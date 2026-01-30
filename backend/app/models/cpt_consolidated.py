"""Model for AMA CPT Consolidated Code List (new table, loaded via COPY)."""

from sqlalchemy import Column, Integer, String, Text

from .base import Base


class CptConsolidated(Base):
    """
    AMA CPT Consolidated Code List.
    Columns match ConsolidatedCodeList.csv order for COPY.
    """

    __tablename__ = "cpt_consolidated"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(Integer, nullable=True, index=True)
    cpt_code = Column(String(20), nullable=False, index=True)
    long_desc = Column(Text, nullable=True)
    medium_desc = Column(Text, nullable=True)
    short_desc = Column(Text, nullable=True)
    consumer_desc = Column(Text, nullable=True)
    spanish_consumer_desc = Column(Text, nullable=True)
    current_descriptor_effective_date = Column(String(20), nullable=True)
    test_name = Column(Text, nullable=True)
    lab_name = Column(Text, nullable=True)
    manufacturer_name = Column(Text, nullable=True)

    def __repr__(self):
        return f"<CptConsolidated(cpt_code={self.cpt_code!r})>"
