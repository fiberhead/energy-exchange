from logging import getLogger
from typing import Dict, Any, Union  # noqa

from d3a.exceptions import SimulationException
from d3a.models.base import AreaBehaviorBase
from d3a.models.events import EventMixin, TriggerMixin, Trigger, AreaEvent, MarketEvent
from d3a.models.market import Market, Offer  # noqa


log = getLogger(__name__)


class _TradeLookerUpper:
    def __init__(self, owner_name):
        self.owner_name = owner_name

    def __getitem__(self, market):
        for trade in market.trades:
            owner_name = self.owner_name
            if trade.seller == owner_name or trade.buyer == owner_name:
                yield trade


class _Offers:
    def __init__(self, strategy):
        self.strategy = strategy
        self.bought = {}  # type: Dict[Offer, Market]
        self.posted = {}  # type: Dict[Offer, Market]
        self.sold = {}  # type: Dict[Offer, Market]

    @property
    def open(self):
        return {id: market for id, market in self.posted.items() if id not in self.sold}

    def post(self, offer, market):
        self.posted[offer] = market

    def replace(self, old_offer, new_offer, market):
        try:
            self.posted.pop(old_offer)
            self.post(new_offer, market)
        except KeyError:
            self.strategy.log.warn("Offer already taken")

    def on_trade(self, market, trade):
        try:
            if trade.offer.seller == self.strategy.owner.name:
                self.sold[trade.offer.id] = market
            if trade.buyer == self.strategy.owner.name:
                self.bought[trade.offer.id] = market
        except AttributeError:
            raise SimulationException("Trade event before strategy was initialized.")


class BaseStrategy(TriggerMixin, EventMixin, AreaBehaviorBase):
    available_triggers = [
        Trigger('enable', state_getter=lambda s: s.enabled, help="Enable trading"),
        Trigger('disable', state_getter=lambda s: not s.enabled, help="Disable trading")
    ]

    def __init__(self):
        super(BaseStrategy, self).__init__()
        self.offers = _Offers(self)
        self.enabled = True

    parameters = None

    def non_attr_parameters(self):
        return dict()

    @property
    def trades(self):
        return _TradeLookerUpper(self.owner.name)

    def energy_balance(self, market, *, allow_open_market=False):
        """
        Return own energy balance for a particular market.

        Negative values indicate bought energy, postive ones sold energy.
        """
        if not allow_open_market and not market.readonly:
            raise ValueError(
                'Energy balance for open market requested and `allow_open_market` no passed')
        return sum(
            t.offer.energy * -1
            if t.buyer == self.owner.name
            else t.offer.energy
            for t in self.trades[market]
        )

    def accept_offer(self, market: Market, offer, *, buyer=None, energy=None):
        if buyer is None:
            buyer = self.owner.name
        trade = market.accept_offer(offer, buyer, energy=energy)
        return trade

    def post(self, **data):
        self.event_data_received(data)

    def event_data_received(self, data: Dict[str, Any]):
        pass

    def trigger_enable(self, **kw):
        self.enabled = True
        self.log.warning("Trading has been enabled")

    def trigger_disable(self):
        self.enabled = False
        self.log.warning("Trading has been disabled")
        # We've been disabled - remove all future open offers
        for market in self.area.markets.values():
            for offer in list(market.offers.values()):
                if offer.seller == self.owner.name:
                    market.delete_offer(offer)

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        if self.enabled or event_type in (AreaEvent.ACTIVATE, MarketEvent.TRADE):
            super().event_listener(event_type, **kwargs)

    def event_trade(self, *, market, trade):
        self.offers.on_trade(market, trade)
