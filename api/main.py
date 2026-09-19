"""Offline API using median earnings four years after completion."""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as PathParameter, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core import analyze
from core.comparisons import compare_paths
from data import CacheError, CacheMissError, ScorecardClient, ScorecardError
from data.comparisons import comparison_catalog
from data.scorecard import ROOT
from .models import AnalysisRequest, AnalysisResponse, MajorsResponse


def create_app(*, seed_dir: Path = ROOT / "seed") -> FastAPI:
    # No API option or environment setting can enable live Scorecard access.
    scorecard = ScorecardClient(seed_dir=seed_dir, allow_network=False)
    app = FastAPI(
        title="Tuition Trap API", version="0.1.0",
        description="Loan consequences using median earnings four years after completion.",
        docs_url=None, redoc_url=None,  # No external CDN requests in offline use.
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Omit raw inputs: NaN/Infinity in rejected input cannot be encoded as JSON.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]})

    @app.exception_handler(CacheMissError)
    async def missing_school(request: Request, exc: CacheMissError):
        return JSONResponse(status_code=404, content={"detail": {
            "code": "school_not_cached",
            "message": "This school is not available in the offline dataset. Choose a seeded demo school.",
        }})

    @app.exception_handler(CacheError)
    @app.exception_handler(ScorecardError)
    async def invalid_data(request: Request, exc: Exception):
        return JSONResponse(status_code=503, content={"detail": {
            "code": "school_data_unavailable",
            "message": "School data could not be read. Restore the committed seed files and retry.",
        }})

    @app.get("/schools/{school_id}/majors", response_model=MajorsResponse)
    def majors(
        school_id: Annotated[int, PathParameter(gt=0)],
        credential_level: Annotated[int, Query(ge=1, le=3)] = 3,
    ):
        """List undergraduate programs with median earnings four years after completion."""
        return scorecard.list_majors(school_id, credential_level=credential_level)

    @app.post("/analyze", response_model=AnalysisResponse)
    def analysis(body: AnalysisRequest):
        """Return loan consequences using cached median earnings four years after completion."""
        choices = scorecard.list_majors(body.school_id, credential_level=body.major.credential_level)
        selected = next((major for major in choices["majors"] if major["code"] == body.major.code), None)
        if selected is None:
            raise HTTPException(status_code=422, detail={
                "code": "major_unavailable",
                "message": "This program has no available median earnings four years after completion at the selected school and credential level. Choose a program returned by the majors endpoint.",
            })
        school = scorecard.get_school(body.school_id)
        result = analyze(
            body.loan_amount,
            selected["median_earnings_four_years_after_completion"],
            **body.overrides.model_dump(),
        )
        return {
            **result,
            "school": {"id": school["id"], "name": school["school"]["name"], "cost": school["latest"].get("cost")},
            "major": selected,
            "data_source": "seed cache",
            "comparisons": compare_paths(
                school, selected, choices["majors"], body.loan_amount,
                **comparison_catalog(scorecard, school, choices["majors"], body.major.credential_level),
                overrides=body.overrides.model_dump(),
            ),
        }

    return app


app = create_app()
