"""
INF1103 Week 11 - Strategy pattern: order discounts
Each discount rule lives in its own class. All of them share ONE method, apply(),
defined by the abstract DiscountStrategy. Order only ever calls apply(), so a new
discount is a new class here - Order never has to change (Open/Closed Principle).
"""
from abc import ABC, abstractmethod


class DiscountStrategy(ABC):
    @abstractmethod
    def apply(self, total: float) -> float:
        """Take an order total and return the discounted total."""


class NoDiscount(DiscountStrategy):
    def apply(self, total: float) -> float:
        return total


class PercentageDiscount(DiscountStrategy):
    def __init__(self, percent: float) -> None:
        if percent < 0 or percent > 100:
            raise ValueError("Percentage must be between 0 and 100.")
        self.__percent: float = percent

    def get_percent(self) -> float:
        return self.__percent

    def apply(self, total: float) -> float:
        return total - total * self.__percent / 100


class BulkDiscount(DiscountStrategy):
    def __init__(self, threshold: float, amount: float) -> None:
        if threshold < 0 or amount < 0:
            raise ValueError("Threshold and amount cannot be negative.")
        self.__threshold: float = threshold
        self.__amount: float = amount

    def apply(self, total: float) -> float:
        if total >= self.__threshold:
            return total - self.__amount
        return total


class StudentDiscount(DiscountStrategy):
    """Fourth strategy (Section 2.4): a flat 5% off. Added WITHOUT touching Order."""
    STUDENT_PERCENT: float = 5.0

    def apply(self, total: float) -> float:
        return total - total * self.STUDENT_PERCENT / 100
