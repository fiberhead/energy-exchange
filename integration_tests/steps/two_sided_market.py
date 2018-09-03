from behave import then
from math import isclose
from d3a.export_unmatched_loads import export_unmatched_loads
from d3a.models.strategy.const import ConstSettings


@then('the load has no unmatched loads')
def no_unmatched_loads(context):
    unmatched = export_unmatched_loads(context.simulation.area)
    assert unmatched["unmatched_load_count"] == 0


@then('the PV always provides constant power according to load demand')
def pv_constant_power(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: "H1 General Load" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pv = next(filter(lambda x: "H2 PV" in x.name, house2.children))

    load_energies_set = set()
    pv_energies_set = set()
    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            if trade.buyer == load.name:
                load_energies_set.add(trade.offer.energy)

    for slot, market in house2.past_markets.items():
        for trade in market.trades:
            if trade.seller == pv.name:
                pv_energies_set.add(trade.offer.energy)

    assert len(load_energies_set) == 1
    assert len(pv_energies_set) == 1
    assert load_energies_set == pv_energies_set


@then('the energy rate for all the trades is the mean of max and min load/pv rate')
def energy_rate_average_between_min_and_max_load_pv(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    load = next(filter(lambda x: "H1 General Load" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pv = next(filter(lambda x: "H2 PV" in x.name, house2.children))

    load_rates_set = set()
    pv_rates_set = set()
    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            if trade.buyer == load.name:
                load_rates_set.add(trade.offer.price / trade.offer.energy)

    for slot, market in house2.past_markets.items():
        for trade in market.trades:
            if trade.seller == pv.name:
                pv_rates_set.add(trade.offer.price / trade.offer.energy)

    rate_threshold = (ConstSettings.LOAD_MAX_ENERGY_RATE - ConstSettings.LOAD_MIN_ENERGY_RATE) / 2
    assert all([int(rate) == int(rate_threshold) for rate in load_rates_set])
    assert all([int(rate) == int(rate_threshold) for rate in pv_rates_set])


@then('the storage is never selling energy')
def storage_never_selling(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    for slot, market in storage.past_markets.items():
        for trade in market.trades:
            assert trade.seller != storage.name
            assert trade.buyer == storage.name


@then('the storage final SOC is {soc_level}%')
def final_soc_full(context, soc_level):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))
    if soc_level == '0':
        soc_level = ConstSettings.STORAGE_MIN_ALLOWED_SOC * 100.0
    final_soc = list(storage.strategy.state.charge_history.values())[-1]
    assert isclose(final_soc, float(soc_level))


@then('the energy rate for all the trades is the mean of max and min pv/storage rate')
def energy_rate_average_between_min_and_max_ess_pv(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    pv = next(filter(lambda x: "H2 PV" in x.name, house2.children))

    storage_rates_set = set()
    pv_rates_set = set()
    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            if trade.buyer == storage.name:
                storage_rates_set.add(trade.offer.price / trade.offer.energy)

    for slot, market in house2.past_markets.items():
        for trade in market.trades:
            if trade.seller == pv.name:
                pv_rates_set.add(trade.offer.price / trade.offer.energy)

    rate_threshold = round(
        (ConstSettings.STORAGE_BREAK_EVEN_BUY - ConstSettings.STORAGE_MIN_BUYING_RATE) / 2
    )

    assert all([int(rate) == int(rate_threshold) for rate in storage_rates_set])
    assert all([int(rate) == int(rate_threshold) for rate in pv_rates_set])


@then('the storage is never buying energy and is always selling energy')
def storage_never_buys_always_sells(context):
    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            assert trade.buyer != storage.name
            assert trade.seller == storage.name


@then('all the trade rates are between break even sell and market maker rate price')
def trade_rates_break_even(context):

    house1 = next(filter(lambda x: x.name == "House 1", context.simulation.area.children))
    storage = next(filter(lambda x: "H1 Storage" in x.name, house1.children))

    house2 = next(filter(lambda x: x.name == "House 2", context.simulation.area.children))
    load = next(filter(lambda x: "H2 General Load" in x.name, house2.children))

    for area in [house1, house2, storage, load]:
        for slot, market in area.past_markets.items():
            for trade in market.trades:
                assert ConstSettings.STORAGE_BREAK_EVEN_SELL <= \
                       trade.offer.price / trade.offer.energy <= \
                       ConstSettings.DEFAULT_MARKET_MAKER_RATE
