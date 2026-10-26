"""Arama ucu (`POST /api/v1/search`): LLM'siz ham arama — kaynak parçalar ve puanları."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.responses import errors
from src.application.schemas.search import SearchRequest, SearchResponse
from src.application.services.retrieval_service import RetrievalService
from src.core.deps import get_current_user, get_retrieval_service

router = APIRouter(tags=["Search & Chat"], dependencies=[Depends(get_current_user)])


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=200,
    summary="Standartlarda ara",
    description="Sorguya en ilgili standart parçalarını puanıyla döner (cevap üretmez). `standard_ids` boşsa tüm "
                "indekslenmiş standartlarda aranır; indekslenmemiş standartlar atlanır. Sonuç yoksa `results` boş.",
    responses=errors(auth=True),
)
def search(body: SearchRequest, svc: Annotated[RetrievalService, Depends(get_retrieval_service)]) -> SearchResponse:
    # TODO(Sudenur): gerçek hibrit arama SearchService arayüzüne takılınca bu uç değişmeden onu kullanır.
    return SearchResponse.model_validate(svc.search(body.query, body.standard_ids, body.top_k, body.mode))
