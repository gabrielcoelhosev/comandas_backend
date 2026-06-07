#Gabriel Coelho Severino
import base64

from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional

class ProdutoCreate(BaseModel):
    nome: str
    descricao: str
    foto: Optional[bytes] = None
    valor_unitario: float

class ProdutoUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    foto: Optional[bytes] = None
    valor_unitario: Optional[float] = None

class ProdutoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    descricao: str
    foto: Optional[bytes] = None
    valor_unitario: float

    @field_serializer('foto')
    def serialize_foto(self, foto: Optional[bytes]):
        if foto is None:
            return None

        return f"data:image/png;base64,{base64.b64encode(foto).decode('ascii')}"
