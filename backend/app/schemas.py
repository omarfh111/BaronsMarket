from typing import List, Optional

from pydantic import BaseModel


class ProductPrediction(BaseModel):
    name: str
    brand: str
    price: float
    image: str
    confidence: Optional[float] = None
    detector_confidence: Optional[float] = None


class DetectResponse(BaseModel):
    predictions: List[ProductPrediction]

