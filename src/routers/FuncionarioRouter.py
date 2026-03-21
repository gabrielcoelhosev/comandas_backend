# Gabriel Coelho Severino

from fastapi import APIRouter
from src.domain.entities.Funcionario import Funcionario

router = APIRouter()

@router.get('/funcionario/', tags=['Funcionário'], status_code=200)
def get_funcinario():
    return {"msg": "funcinario get todos executado"}

@router.get('/funcinario/{id}', tags=["Funcionário"], status_code=200)
def get_funcinario(id: int):
    return {"msg": "funciomario get um executado"}

@router.post('/funcionario', tags=['Funcionário'], status_code=200)
def post_funcionario(corpo: Funcionario):
    return {"msg": "funcionario post executado", "nome": corpo.nome, "cpf": corpo.cpf, "telefone": corpo.telefone}

@router.put('/funcionario/{id}', tags=['Funcionário'], status_code=200)
def put_funcionario(id: int, corpo: Funcionario):
    return {"msg": "funcionario put executado", "nome": corpo.nome, "cpf": corpo.cpf, "telefone": corpo.telefone}

@router.delete('/funcionario/{id}', tags=['Funcionário'], status_code=200)
def delete_funcionario(id: int):
    return {"msg": "funcionario delete executado", "id":id}