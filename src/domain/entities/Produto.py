from pydantic import BaseModel

class Produto(BaseModel):
    id_produto: int
    nome: str
    descricao: str
    foto: bytes
    valor_unitario: float
    