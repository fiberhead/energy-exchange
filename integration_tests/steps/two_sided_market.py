"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from behave import then
from math import isclose
from d3a_interface.sim_results.export_unmatched_loads import MarketUnmatchedLoads, \
    get_number_of_unmatched_loads
from d3a.models.market.market_structures import Offer, Bid


@then('there should be no unmatched loads')
@then('the load has no unmatched loads')
def no_unmatched_loads(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    count = 0
    unmatched = MarketUnmatchedLoads()
    for time_slot, core_stats in context.raw_sim_data.items():
        unmatched.update(
            context.area_tree_summary_data, core_stats, time_slot
        )
        unmatched_data, _ = unmatched.export_unmatched_loads.get_current_market_results(
            context.area_tree_summary_data, core_stats, time_slot
        )
        count += 1
        assert get_number_of_unmatched_loads(unmatched_data) == 0
    assert count > 0


@then('the load has unmatched loads')
def has_unmatched_loads(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    count = 0
    unmatched = MarketUnmatchedLoads()
    for time_slot, core_stats in context.raw_sim_data.items():
        unmatched.update(
            context.area_tree_summary_data, core_stats, time_slot
        )
        unmatched_data, _ = unmatched.export_unmatched_loads.get_current_market_results(
            context.area_tree_summary_data, core_stats, time_slot
        )
        if get_number_of_unmatched_loads(unmatched_data) > 0:
            count += 1
    assert count > 0


@then('the {device} bid is partially fulfilled by the PV offers')
def device_partially_fulfill_bid(context, device):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)

    for time_slot, core_stats in context.raw_sim_data.items():
        grid_trades = core_stats[context.name_uuid_map['Grid']]['trades']
        house1_trades = core_stats[context.name_uuid_map['House 1']]['trades']
        house2_trades = core_stats[context.name_uuid_map['House 2']]['trades']
        if len(house1_trades) == 0:
            continue

        # Assert one trade for each PV
        assert len(house1_trades) == 5
        assert all(trade['buyer'] == device for trade in house1_trades)
        assert all(trade['seller'] == "IAA House 1" for trade in house1_trades)
        assert len(grid_trades) == 5
        assert all(trade['buyer'] == "IAA House 1" for trade in grid_trades)
        assert all(trade['seller'] == "IAA House 2" for trade in grid_trades)

        pv_names = ['H2 PV1', 'H2 PV2', 'H2 PV3', 'H2 PV4', 'H2 PV5']
        assert all(trade['buyer'] == "IAA House 2" for trade in house2_trades)
        assert all(trade['seller'] in pv_names for trade in house2_trades)


@then('the PV always provides constant power according to load demand')
def pv_constant_power(context):
    from d3a_interface.utils import get_area_name_uuid_mapping
    context.name_uuid_map = get_area_name_uuid_mapping(context.area_tree_summary_data)
    load_energies_set = set()
    pv_energies_set = set()

    for time_slot, core_stats in context.raw_sim_data.items():
        for trade in core_stats[context.name_uuid_map['House 1']]['trades']:
            if trade['buyer'] == "H1 General Load":
                load_energies_set.add(trade['energy'])
        for trade in core_stats[context.name_uuid_map['House 2']]['trades']:
            if trade['seller'] == 'H2 PV':
                pv_energies_set.add(trade['energy'])

    assert len(load_energies_set) == 1
    assert len(pv_energies_set) == 1
    assert load_energies_set == pv_energies_set


@then('the storage is never selling energy')
def storage_never_selling(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    for time_slot, core_stats in context.raw_sim_data.items():
        for trade in core_stats[context.name_uuid_map['House 1']]['trades']:
            assert trade['seller'] != "H1 Storage"
            assert trade['buyer'] == "H1 Storage"


@then('the storage final SOC is {soc_level}%')
def final_soc_full(context, soc_level):
    for time_slot, core_stats in context.raw_sim_data.items():
        if time_slot[-5:] == "23:00":
            assert isclose(float(soc_level),
                           core_stats[context.name_uuid_map['H1 Storage']]['soc_history_%'])


@then('the energy rate for all trades are in between initial and final buying rate of storage')
def energy_rate_average_between_min_and_max_ess_pv(context):
    for time_slot, core_stats in context.raw_sim_data.items():
        for area_uuid, area_stats in core_stats.items():
            for trade in area_stats['trades']:
                assert 0.0 <= trade['energy_rate'] <= 24.9


@then('the storage is never buying energy and is always selling energy')
def storage_never_buys_always_sells(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    for time_slot, core_stats in context.raw_sim_data.items():
        house1_core_stats = core_stats[context.name_uuid_map['House 1']]
        for trade in house1_core_stats['trades']:
            assert trade['buyer'] != "H1 Storage"
            assert trade['seller'] == "H1 Storage"


@then('all the trade rates are between load device buying boundaries')
def trade_rates_break_even(context):
    for time_slot, core_stats in context.raw_sim_data.items():
        for area_uuid, area_stats in core_stats.items():
            for trade in area_stats['trades']:
                assert 0.0 <= trade['energy_rate'] <= 35.0


@then('CEP posted the residual offer at the old rate')
def cep_offer_residual_offer_rate(context):
    house = next(filter(lambda x: "House" in x.name, context.simulation.area.children))
    cep = next(filter(lambda x: "Commercial Energy Producer" in x.name, house.children))

    for market in house.past_markets:
        if len(market.trades) > 0:
            for id, offer in market.offers.items():
                assert isclose((offer.price / offer.energy),
                               cep.strategy.energy_rate[market.time_slot])


@then('Energy producer is {producer} & consumer is {consumer}')
def energy_origin(context, producer, consumer):
    trade_count = 0
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)

    for time_slot, core_stats in context.raw_sim_data.items():
        for trade in core_stats[context.name_uuid_map['Grid']]['trades']:
            trade_count += 1
            assert trade['buyer_origin'] == consumer
            assert trade['seller_origin'] == producer

    assert trade_count > 0


@then('trades are matched only on the Grid market')
def trades_matched_on_grid(context):
    # Assert that all grid trades contain Offer objects, bid trades are not tracked
    assert all(isinstance(trade.offer, Offer)
               for market in context.simulation.area.past_markets
               for trade in market.trades)

    # Assert that all House 1 trades contain Bid objects
    house1 = next(c for c in context.simulation.area.children if c.name == "House 1")
    load = next(c for c in house1.children if c.name == "H1 General Load")
    load_energy_per_day = load.strategy.energy_per_slot_Wh / 1000 * 24
    house1_consumed_energy = sum(trade.offer.energy
                                 for market in house1.past_markets
                                 for trade in market.trades)
    assert isclose(house1_consumed_energy, load_energy_per_day, rel_tol=1e-3)

    # Assert that all House 2 trades contain Offer objects
    house2 = next(c for c in context.simulation.area.children if c.name == "House 2")
    assert all(isinstance(trade.offer, Offer)
               for market in house2.past_markets
               for trade in market.trades)

    house2_consumed_energy = sum(trade.offer.energy
                                 for market in house2.past_markets
                                 for trade in market.trades)
    assert isclose(house2_consumed_energy, load_energy_per_day, rel_tol=1e-3)


@then('trades are matched only on the House 1 market')
def trades_matched_on_house1(context):
    # Assert that all grid trades contain Offer objects, bid trades are not tracked
    assert all(isinstance(trade.offer, Offer)
               for market in context.simulation.area.past_markets
               for trade in market.trades)

    # Assert that all House 1 trades contain Offer objects
    house1 = next(c for c in context.simulation.area.children if c.name == "House 1")
    load = next(c for c in house1.children if c.name == "H1 General Load")
    load_energy_per_day = load.strategy.energy_per_slot_Wh / 1000 * 24
    assert all(isinstance(trade.offer, Offer)
               for market in house1.past_markets
               for trade in market.trades)

    house1_consumed_energy = sum(trade.offer.energy
                                 for market in house1.past_markets
                                 for trade in market.trades)
    assert isclose(house1_consumed_energy, load_energy_per_day, rel_tol=1e-3)

    # Assert that all House 2 trades contain Offer objects
    house2 = next(c for c in context.simulation.area.children if c.name == "House 2")
    assert all(isinstance(trade.offer, Offer)
               for market in house2.past_markets
               for trade in market.trades)


@then('trades are matched only on the House 2 market')
def trades_matched_on_house2(context):
    # Assert that all grid trades contain Bid objects
    assert all(isinstance(trade.offer, Bid)
               for market in context.simulation.area.past_markets
               for trade in market.trades)

    # Assert that all House 1 trades contain Bid objects
    house1 = next(c for c in context.simulation.area.children if c.name == "House 1")
    load = next(c for c in house1.children if c.name == "H1 General Load")
    load_energy_per_day = load.strategy.energy_per_slot_Wh / 1000 * 24
    assert all(isinstance(trade.offer, Bid)
               for market in house1.past_markets
               for trade in market.trades)

    # Assert that all House 2 trades contain Offer objects
    house2 = next(c for c in context.simulation.area.children if c.name == "House 2")
    assert all(isinstance(trade.offer, Offer)
               for market in house2.past_markets
               for trade in market.trades)
    house2_consumed_energy = sum(trade.offer.energy
                                 for market in house2.past_markets
                                 for trade in market.trades)
    assert isclose(house2_consumed_energy, load_energy_per_day, rel_tol=1e-3)
