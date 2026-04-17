from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    project_id: int
    use_cleaned: bool = True
