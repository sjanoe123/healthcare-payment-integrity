"""Rule registry for managing active rules."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import RuleContext, RuleHit

RuleCallable = Callable[[RuleContext], list[RuleHit]]


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: list[RuleCallable] = []

    def register(self, rule: RuleCallable) -> None:
        if rule not in self._rules:
            self._rules.append(rule)

    def extend(self, rules: Iterable[RuleCallable]) -> None:
        for rule in rules:
            self.register(rule)

    def active_rules(self) -> Iterable[RuleCallable]:
        return tuple(self._rules)


default_registry = RuleRegistry()
