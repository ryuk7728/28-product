from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.bots.bid_policy import BidPolicyConfig, BidThresholds
from app.engine.k_policy import KPolicyConfig, KPolicyMode


class BidThresholdsRequest(BaseModel):
    opening15: int = Field(ge=0, le=100)
    opening16: int = Field(ge=0, le=100)
    laterBid: int = Field(ge=0, le=100)
    jumpTo16: int = Field(ge=0, le=100)

    def to_domain(self) -> BidThresholds:
        return BidThresholds(
            opening_15=self.opening15,
            opening_16=self.opening16,
            later_bid=self.laterBid,
            jump_to_16=self.jumpTo16,
        )


class BidPolicyRequest(BaseModel):
    mode: Literal["aggressive", "optimal", "custom"] = "aggressive"
    positionAware: bool = False
    thresholds: BidThresholdsRequest | None = None

    @model_validator(mode="after")
    def validate_custom_thresholds(self) -> BidPolicyRequest:
        if self.mode == "custom" and self.thresholds is None:
            raise ValueError("Custom bidding mode requires all four thresholds.")
        return self

    def to_domain(self) -> BidPolicyConfig:
        if self.mode == "aggressive":
            return BidPolicyConfig.aggressive(position_aware=self.positionAware)
        if self.mode == "optimal":
            return BidPolicyConfig.optimal(position_aware=self.positionAware)
        assert self.thresholds is not None
        return BidPolicyConfig.custom(
            self.thresholds.to_domain(), position_aware=self.positionAware
        )


def resolve_bid_policy(request: BidPolicyRequest | None) -> BidPolicyConfig:
    return request.to_domain() if request is not None else BidPolicyConfig.aggressive()


def resolve_k_policy(mode: KPolicyMode | None) -> KPolicyConfig:
    return KPolicyConfig(mode=mode or "regular")
