import ast
import json
import logging
import pickle
from datetime import datetime, date
from zlib import decompress

import d3a.constants
from d3a.d3a_core.simulation import run_simulation
from d3a.d3a_core.util import available_simulation_scenarios, update_advanced_settings
from d3a.models.config import SimulationConfig
from d3a_interface.constants_limits import GlobalConfig, ConstSettings
from d3a_interface.enums import BidOfferMatchAlgoEnum, SpotMarketTypeEnum
from d3a_interface.settings_validators import validate_global_settings
from pendulum import duration, instance

log = logging.getLogger()


def decompress_and_decode_queued_strings(queued_string):
    return pickle.loads(decompress(queued_string))


def launch_simulation_from_rq_job(scenario, settings, events, aggregator_device_mapping,
                                  saved_state, job_id):
    logging.getLogger().setLevel(logging.ERROR)
    scenario = decompress_and_decode_queued_strings(scenario)
    d3a.constants.CONFIGURATION_ID = scenario.pop("configuration_uuid")
    if "collaboration_uuid" in scenario:
        d3a.constants.EXTERNAL_CONNECTION_WEB = True
        GlobalConfig.IS_CANARY_NETWORK = scenario.pop("is_canary_network", False)
        d3a.constants.RUN_IN_REALTIME = GlobalConfig.IS_CANARY_NETWORK
    saved_state = decompress_and_decode_queued_strings(saved_state)
    log.error(f"Starting simulation with job_id: {job_id}")

    try:
        if settings is None:
            settings = {}
        else:
            settings = {k: v for k, v in settings.items() if v is not None and v != "None"}

        advanced_settings = settings.get('advanced_settings', None)
        if advanced_settings is not None:
            update_advanced_settings(ast.literal_eval(advanced_settings))
        aggregator_device_mapping = json.loads(aggregator_device_mapping)

        if events is not None:
            events = ast.literal_eval(events)

        config_settings = {
            "start_date":
                instance(datetime.combine(settings.get('start_date'), datetime.min.time()))
                if 'start_date' in settings else GlobalConfig.start_date,
            "sim_duration":
                duration(days=settings['duration'].days)
                if 'duration' in settings else GlobalConfig.sim_duration,
            "slot_length":
                duration(seconds=settings['slot_length'].seconds)
                if 'slot_length' in settings else GlobalConfig.slot_length,
            "tick_length":
                duration(seconds=settings['tick_length'].seconds)
                if 'tick_length' in settings else GlobalConfig.tick_length,
            "market_maker_rate":
                settings.get('market_maker_rate',
                             str(ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE)),
            "market_count": settings.get('market_count', GlobalConfig.market_count),
            "cloud_coverage": settings.get('cloud_coverage', GlobalConfig.cloud_coverage),
            "pv_user_profile": settings.get('pv_user_profile', None),
            "max_panel_power_W": settings.get('max_panel_power_W',
                                              ConstSettings.PVSettings.MAX_PANEL_OUTPUT_W),
            "grid_fee_type": settings.get('grid_fee_type', GlobalConfig.grid_fee_type),
            "external_connection_enabled": settings.get('external_connection_enabled', False),
            "aggregator_device_mapping": aggregator_device_mapping
        }

        if GlobalConfig.IS_CANARY_NETWORK:
            config_settings['start_date'] = \
                instance((datetime.combine(date.today(), datetime.min.time())))

        validate_global_settings(config_settings)

        slot_length_realtime = duration(seconds=settings['slot_length_realtime'].seconds) \
            if 'slot_length_realtime' in settings else None

        config = SimulationConfig(**config_settings)

        spot_market_type = settings.get('spot_market_type', None)
        if spot_market_type is not None:
            if spot_market_type == SpotMarketTypeEnum.ONE_SIDED.value:
                ConstSettings.IAASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value
            if spot_market_type == SpotMarketTypeEnum.TWO_SIDED_PAY_AS_BID.value:
                ConstSettings.IAASettings.MARKET_TYPE = (
                    SpotMarketTypeEnum.TWO_SIDED_PAY_AS_BID.value)
                ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = (
                    BidOfferMatchAlgoEnum.PAY_AS_BID.value)
            if spot_market_type == SpotMarketTypeEnum.TWO_SIDED_PAY_AS_CLEAR.value:
                ConstSettings.IAASettings.MARKET_TYPE = (
                    SpotMarketTypeEnum.TWO_SIDED_PAY_AS_BID.value)
                ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = \
                    BidOfferMatchAlgoEnum.PAY_AS_CLEAR.value
            if spot_market_type == SpotMarketTypeEnum.TWO_SIDED_EXTERNAL.value:
                ConstSettings.IAASettings.MARKET_TYPE = (
                    SpotMarketTypeEnum.TWO_SIDED_PAY_AS_BID.value)
                ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = \
                    BidOfferMatchAlgoEnum.EXTERNAL.value

        if scenario is None:
            scenario_name = "default_2a"
        elif scenario in available_simulation_scenarios:
            scenario_name = scenario
        else:
            scenario_name = 'json_arg'
            config.area = scenario

        kwargs = {"no_export": True,
                  "pricing_scheme": 0,
                  "seed": settings.get('random_seed', 0)}

        d3a.constants.CONNECT_TO_PROFILES_DB = True

        run_simulation(setup_module_name=scenario_name,
                       simulation_config=config,
                       simulation_events=events,
                       redis_job_id=job_id,
                       saved_sim_state=saved_state,
                       slot_length_realtime=slot_length_realtime,
                       kwargs=kwargs)
    except Exception:
        import traceback
        from d3a.d3a_core.redis_connections.redis_communication import publish_job_error_output
        publish_job_error_output(job_id, traceback.format_exc())
        logging.getLogger().error(f"Error on jobId {job_id}: {traceback.format_exc()}")
