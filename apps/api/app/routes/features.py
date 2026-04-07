from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import User
from app.services.cleaner import clean_dataset
from app.services.feature_engineer import create_feature, suggest_features
from app.services.file_loader import load_dataset
from app.services.serializers import to_jsonable
from app.state import PROJECT_FILES

router = APIRouter(prefix="/features", tags=["features"])


def _load(project_id: int):
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="No uploaded file for this project.")
    path = PROJECT_FILES[project_id]["path"]
    try:
        df = load_dataset(path)
        df_clean, _, _ = clean_dataset(df)
        return df_clean
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {e}")


class FeatureRequest(BaseModel):
    project_id: int
    name: str
    formula: str


@router.post("/create")
def feature_create(req: FeatureRequest, current_user: User = Depends(get_current_user)):
    df = _load(req.project_id)
    try:
        result = create_feature(df, req.name, req.formula)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature creation failed: {e}")

    # persist in project state
    if "features" not in PROJECT_FILES[req.project_id]:
        PROJECT_FILES[req.project_id]["features"] = {}
    PROJECT_FILES[req.project_id]["features"][req.name] = {
        "formula": req.formula,
        "dtype": result["dtype"],
        "values": result.pop("series_values"),
    }

    return to_jsonable(result)


@router.get("/suggest")
def feature_suggest(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    df = _load(project_id)
    try:
        suggestions = suggest_features(df)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {e}")


@router.get("/list")
def feature_list(project_id: int = Query(...), current_user: User = Depends(get_current_user)):
    if project_id not in PROJECT_FILES:
        raise HTTPException(status_code=404, detail="Project not found.")
    features = PROJECT_FILES[project_id].get("features", {})
    return {
        "features": [
            {"name": name, "formula": meta["formula"], "dtype": meta["dtype"]}
            for name, meta in features.items()
        ]
    }
