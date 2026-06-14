from pydantic import BaseModel


class DocumentSearchHitResponse(BaseModel):
    document_id: str
    node_id: str
    node_title: str
    match_index: int
    match_length: int
    matched_text: str
    snippet: str
    match_source: str
    total_matches_in_document: int
    occurrence_index: int | None = None
