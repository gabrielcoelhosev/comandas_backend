from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.schemas.AuthSchema import FuncionarioAuth
from domain.schemas.ClienteSchema import ClienteResponse
from domain.schemas.ComandaSchema import FuncionarioResponse, ProdutoResponse
from domain.schemas.RecebimentoSchema import (
    CaixaComandaDetalhe,
    CaixaComandaItem,
    CaixaComandaResumo,
    RecebimentoComprovante,
    RecebimentoCreate,
    RecebimentoResponse,
    RecebimentoUpdate,
)
from infra.database import get_async_db
from infra.dependencies import require_group
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.orm.RecebimentoModel import RecebimentoComandaDB, RecebimentoDB
from infra.rate_limit import limiter

router = APIRouter()


def _money(value) -> float:
    return float(value or 0)


def _funcionario_response(funcionario: Optional[FuncionarioDB]) -> Optional[FuncionarioResponse]:
    if not funcionario:
        return None

    return FuncionarioResponse(
        id=funcionario.id,
        nome=funcionario.nome,
        matricula=funcionario.matricula,
        cpf=funcionario.cpf,
        telefone=funcionario.telefone,
        grupo=funcionario.grupo,
    )


def _cliente_response(cliente: Optional[ClienteDB]) -> Optional[ClienteResponse]:
    if not cliente:
        return None

    return ClienteResponse(
        id=cliente.id,
        nome=cliente.nome,
        cpf=cliente.cpf,
        telefone=cliente.telefone,
    )


async def _get_comanda_total(db: AsyncSession, comanda_id: int) -> tuple[float, int]:
    result = await db.execute(
        select(
            func.coalesce(func.sum(ComandaProdutoDB.quantidade * ComandaProdutoDB.valor_unitario), 0),
            func.count(ComandaProdutoDB.id),
        ).where(ComandaProdutoDB.comanda_id == comanda_id)
    )
    total, itens_count = result.one()
    return _money(total), int(itens_count or 0)


async def _build_comanda_resumo(db: AsyncSession, comanda: ComandaDB, funcionario: Optional[FuncionarioDB], cliente: Optional[ClienteDB]) -> CaixaComandaResumo:
    total, itens_count = await _get_comanda_total(db, comanda.id)
    return CaixaComandaResumo(
        id=comanda.id,
        comanda=comanda.comanda,
        data_hora=comanda.data_hora,
        status=comanda.status,
        cliente_id=comanda.cliente_id,
        cliente=_cliente_response(cliente),
        funcionario_id=comanda.funcionario_id,
        funcionario=_funcionario_response(funcionario),
        total=total,
        itens_count=itens_count,
    )


async def _build_comanda_detalhe(db: AsyncSession, comanda: ComandaDB, funcionario: Optional[FuncionarioDB], cliente: Optional[ClienteDB]) -> CaixaComandaDetalhe:
    resumo = await _build_comanda_resumo(db, comanda, funcionario, cliente)
    result = await db.execute(
        select(ComandaProdutoDB, ProdutoDB)
        .outerjoin(ProdutoDB, ProdutoDB.id == ComandaProdutoDB.produto_id)
        .where(ComandaProdutoDB.comanda_id == comanda.id)
        .order_by(ComandaProdutoDB.id)
    )

    itens = []
    for item, produto in result.all():
        produto_response = None
        if produto:
            produto_response = ProdutoResponse(
                id=produto.id,
                nome=produto.nome,
                descricao=produto.descricao,
                foto=produto.foto,
                valor_unitario=produto.valor_unitario,
            )
        itens.append(
            CaixaComandaItem(
                id=item.id,
                produto_id=item.produto_id,
                produto=produto_response,
                quantidade=item.quantidade,
                valor_unitario=_money(item.valor_unitario),
                valor_total=_money(item.quantidade * item.valor_unitario),
            )
        )

    return CaixaComandaDetalhe(**resumo.model_dump(), itens=itens)


async def _get_comandas_by_ids(db: AsyncSession, ids: List[int]):
    result = await db.execute(
        select(ComandaDB, FuncionarioDB, ClienteDB)
        .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
        .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
        .where(ComandaDB.id.in_(ids))
    )
    rows = result.all()
    found_ids = {comanda.id for comanda, _, _ in rows}
    missing_ids = set(ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comanda(s) não encontrada(s): {', '.join(map(str, sorted(missing_ids)))}",
        )
    return rows


async def _get_recebimento_comanda_ids(db: AsyncSession, recebimento_id: int) -> List[int]:
    result = await db.execute(
        select(RecebimentoComandaDB.comanda_id)
        .where(RecebimentoComandaDB.recebimento_id == recebimento_id)
        .order_by(RecebimentoComandaDB.comanda_id)
    )
    return list(result.scalars().all())


async def _build_recebimento_response(db: AsyncSession, recebimento: RecebimentoDB) -> RecebimentoResponse:
    funcionario = None
    cliente = None

    result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id))
    funcionario = result.scalar_one_or_none()

    if recebimento.cliente_id:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id == recebimento.cliente_id))
        cliente = result.scalar_one_or_none()

    return RecebimentoResponse(
        id=recebimento.id,
        funcionario_id=recebimento.funcionario_id,
        funcionario=_funcionario_response(funcionario),
        cliente_id=recebimento.cliente_id,
        cliente=_cliente_response(cliente),
        valor_bruto=_money(recebimento.valor_bruto),
        desconto=_money(recebimento.desconto),
        acrescimo=_money(recebimento.acrescimo),
        valor_total=_money(recebimento.valor_total),
        data_hora=recebimento.data_hora,
        comanda_ids=await _get_recebimento_comanda_ids(db, recebimento.id),
    )


async def _validate_funcionario_cliente(db: AsyncSession, funcionario_id: int, cliente_id: Optional[int]) -> None:
    result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == funcionario_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")

    if cliente_id:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id == cliente_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente não encontrado")


@router.get("/recebimento/dashboard", response_model=List[CaixaComandaResumo], tags=["Recebimento"], summary="Dashboard de comandas abertas - grupos 1 e 3")
@limiter.limit("moderate")
async def get_dashboard_comandas(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(
        select(ComandaDB, FuncionarioDB, ClienteDB)
        .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
        .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
        .where(ComandaDB.status == 0)
        .order_by(ComandaDB.data_hora.desc())
    )
    return [await _build_comanda_resumo(db, comanda, funcionario, cliente) for comanda, funcionario, cliente in result.all()]


@router.get("/recebimento/comandas/detalhe/{ids}", response_model=List[CaixaComandaDetalhe], tags=["Recebimento"], summary="Detalhar comandas para conferência - grupos 1 e 3")
@limiter.limit("moderate")
async def get_comandas_detalhe(
    ids: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    try:
        comanda_ids = [int(value) for value in ids.split(",") if value.strip()]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe IDs de comandas separados por vírgula")

    if not comanda_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe pelo menos uma comanda")

    rows = await _get_comandas_by_ids(db, comanda_ids)
    return [await _build_comanda_detalhe(db, comanda, funcionario, cliente) for comanda, funcionario, cliente in rows]


@router.get("/recebimento/", response_model=List[RecebimentoResponse], tags=["Recebimento"], summary="Listar recebimentos - grupos 1 e 3")
@limiter.limit("moderate")
async def get_recebimentos(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(select(RecebimentoDB).order_by(RecebimentoDB.data_hora.desc()).offset(skip).limit(limit))
    return [await _build_recebimento_response(db, recebimento) for recebimento in result.scalars().all()]


@router.get("/recebimento/{id}", response_model=RecebimentoResponse, tags=["Recebimento"], summary="Buscar recebimento - grupos 1 e 3")
@limiter.limit("moderate")
async def get_recebimento(
    id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebimento não encontrado")

    return await _build_recebimento_response(db, recebimento)


@router.post("/recebimento/", response_model=RecebimentoResponse, status_code=status.HTTP_201_CREATED, tags=["Recebimento"], summary="Novo recebimento - grupos 1 e 3")
@router.post("/recebimento/completo", response_model=RecebimentoResponse, status_code=status.HTTP_201_CREATED, tags=["Recebimento"], summary="Processar recebimento completo - grupos 1 e 3")
@limiter.limit("restrictive")
async def create_recebimento(
    recebimento_data: RecebimentoCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    funcionario_id = recebimento_data.funcionario_id or current_user.id
    desconto = Decimal(str(recebimento_data.desconto or 0))
    acrescimo = Decimal(str(recebimento_data.acrescimo or 0))

    if desconto < 0 or acrescimo < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Desconto e acréscimo não podem ser negativos")

    await _validate_funcionario_cliente(db, funcionario_id, recebimento_data.cliente_id)
    rows = await _get_comandas_by_ids(db, recebimento_data.comanda_ids)

    for comanda, _, _ in rows:
        if comanda.status != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Comanda {comanda.comanda} não está aberta")

    valor_bruto = Decimal("0")
    for comanda, _, _ in rows:
        total, _ = await _get_comanda_total(db, comanda.id)
        valor_bruto += Decimal(str(total))

    valor_total = valor_bruto - desconto + acrescimo
    if valor_total < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valor total final não pode ser negativo")

    try:
        recebimento = RecebimentoDB(
            funcionario_id=funcionario_id,
            cliente_id=recebimento_data.cliente_id,
            valor_bruto=valor_bruto,
            desconto=desconto,
            acrescimo=acrescimo,
            valor_total=valor_total,
            data_hora=datetime.now(),
        )
        db.add(recebimento)
        await db.flush()

        for comanda, _, _ in rows:
            comanda.status = 1
            comanda.funcionario_id = funcionario_id
            if recebimento_data.cliente_id:
                comanda.cliente_id = recebimento_data.cliente_id
            db.add(RecebimentoComandaDB(recebimento_id=recebimento.id, comanda_id=comanda.id))

        await db.commit()
        await db.refresh(recebimento)
        return await _build_recebimento_response(db, recebimento)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar recebimento: {str(e)}")


@router.put("/recebimento/{id}", response_model=RecebimentoResponse, tags=["Recebimento"], summary="Editar recebimento - grupo 1")
@limiter.limit("restrictive")
async def update_recebimento(
    id: int,
    recebimento_data: RecebimentoUpdate,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebimento não encontrado")

    funcionario_id = recebimento_data.funcionario_id or recebimento.funcionario_id
    cliente_id = recebimento_data.cliente_id if recebimento_data.cliente_id is not None else recebimento.cliente_id
    desconto = Decimal(str(recebimento_data.desconto if recebimento_data.desconto is not None else recebimento.desconto))
    acrescimo = Decimal(str(recebimento_data.acrescimo if recebimento_data.acrescimo is not None else recebimento.acrescimo))

    if desconto < 0 or acrescimo < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Desconto e acréscimo não podem ser negativos")

    await _validate_funcionario_cliente(db, funcionario_id, cliente_id)
    valor_total = Decimal(str(recebimento.valor_bruto)) - desconto + acrescimo
    if valor_total < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valor total final não pode ser negativo")

    try:
        recebimento.funcionario_id = funcionario_id
        recebimento.cliente_id = cliente_id
        recebimento.desconto = desconto
        recebimento.acrescimo = acrescimo
        recebimento.valor_total = valor_total
        await db.commit()
        await db.refresh(recebimento)
        return await _build_recebimento_response(db, recebimento)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar recebimento: {str(e)}")


@router.delete("/recebimento/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Recebimento"], summary="Excluir recebimento - grupo 1")
@limiter.limit("critical")
async def delete_recebimento(
    id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebimento não encontrado")

    try:
        result = await db.execute(select(RecebimentoComandaDB).where(RecebimentoComandaDB.recebimento_id == id))
        for vinculo in result.scalars().all():
            await db.delete(vinculo)

        await db.delete(recebimento)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao excluir recebimento: {str(e)}")


@router.get("/recebimento/comprovante/{id}", response_model=RecebimentoComprovante, tags=["Recebimento"], summary="Comprovante de pagamento - grupos 1 e 3")
@limiter.limit("moderate")
async def get_comprovante(
    id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(require_group([1, 3])),
):
    result = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
    recebimento = result.scalar_one_or_none()
    if not recebimento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebimento não encontrado")

    response = await _build_recebimento_response(db, recebimento)
    rows = await _get_comandas_by_ids(db, response.comanda_ids)
    comandas = [await _build_comanda_detalhe(db, comanda, funcionario, cliente) for comanda, funcionario, cliente in rows]
    return RecebimentoComprovante(**response.model_dump(), comandas=comandas)
