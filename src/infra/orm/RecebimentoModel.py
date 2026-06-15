from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer
from infra.database import Base


class RecebimentoDB(Base):
    __tablename__ = "tb_recebimento"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    funcionario_id = Column(Integer, ForeignKey("tb_funcionario.id", ondelete="RESTRICT"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("tb_cliente.id", ondelete="RESTRICT"), nullable=True)
    valor_bruto = Column(DECIMAL(10, 2), nullable=False, default=0)
    desconto = Column(DECIMAL(10, 2), nullable=False, default=0)
    acrescimo = Column(DECIMAL(10, 2), nullable=False, default=0)
    valor_total = Column(DECIMAL(10, 2), nullable=False, default=0)
    data_hora = Column(DateTime, nullable=False)


class RecebimentoComandaDB(Base):
    __tablename__ = "tb_recebimento_comanda"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    recebimento_id = Column(Integer, ForeignKey("tb_recebimento.id", ondelete="RESTRICT"), nullable=False)
    comanda_id = Column(Integer, ForeignKey("tb_comanda.id", ondelete="RESTRICT"), nullable=False)
