from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.schemas.ClienteSchema import ClienteResponse
from domain.schemas.FuncionarioSchema import FuncionarioResponse
from domain.schemas.ProdutoSchema import ProdutoResponse


class RecebimentoCreate(BaseModel):
    comanda_ids: List[int] = Field(min_length=1)
    funcionario_id: Optional[int] = None
    cliente_id: Optional[int] = None
    desconto: float = 0
    acrescimo: float = 0


class RecebimentoUpdate(BaseModel):
    funcionario_id: Optional[int] = None
    cliente_id: Optional[int] = None
    desconto: Optional[float] = None
    acrescimo: Optional[float] = None


class CaixaComandaResumo(BaseModel):
    id: int
    comanda: str
    data_hora: datetime
    status: int
    cliente_id: Optional[int] = None
    cliente: Optional[ClienteResponse] = None
    funcionario_id: int
    funcionario: Optional[FuncionarioResponse] = None
    total: float
    itens_count: int


class CaixaComandaItem(BaseModel):
    id: int
    produto_id: int
    produto: Optional[ProdutoResponse] = None
    quantidade: int
    valor_unitario: float
    valor_total: float


class CaixaComandaDetalhe(CaixaComandaResumo):
    itens: List[CaixaComandaItem] = []


class RecebimentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    funcionario_id: int
    funcionario: Optional[FuncionarioResponse] = None
    cliente_id: Optional[int] = None
    cliente: Optional[ClienteResponse] = None
    valor_bruto: float
    desconto: float
    acrescimo: float
    valor_total: float
    data_hora: datetime
    comanda_ids: List[int] = []


class RecebimentoComprovante(RecebimentoResponse):
    comandas: List[CaixaComandaDetalhe] = []
