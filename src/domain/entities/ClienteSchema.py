# Gabriel Coelho Severino

from pydantic import BaseModel
from typing import Optional

class Cliente(BaseModel):
    nome: str
    cpf: str
    telefone: str

class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    cpf: Optional[str] = None
    telefone: Optional[str] = None

class ClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cpf: str
    telefone: str