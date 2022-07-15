from gsy_framework.read_user_profile import InputProfileTypes, convert_identity_profile_to_float

from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import should_read_profile_from_db


class EnergyProfile:
    """Manage reading/rotating energy profile of an asset."""
    def __init__(self, input_profile=None, input_profile_uuid=None, input_energy_rate=None):
        self.input_profile = input_profile
        self.input_profile_uuid = input_profile_uuid
        self.input_energy_rate = input_energy_rate

        if should_read_profile_from_db(self.input_profile_uuid):
            self.input_profile = None
            self.input_energy_rate = None
        elif input_energy_rate:
            self.input_profile = None
            self.input_profile_uuid = None
        else:
            self.input_profile_uuid = None
            self.input_energy_rate = None

        self.profile = None

    def read_or_rotate_profiles(self, reconfigure=False):
        """Rotate current profile or read and preprocess profile from source."""
        if not self.profile or reconfigure:
            profile = self.input_energy_rate or self.input_profile
        else:
            profile = self.profile

        if self.input_energy_rate is not None:
            profile_type = InputProfileTypes.IDENTITY
        else:
            profile_type = InputProfileTypes.POWER

        profile = global_objects.profiles_handler.rotate_profile(
            profile_type=profile_type,
            profile=profile,
            profile_uuid=self.input_profile_uuid)

        if profile_type == InputProfileTypes.IDENTITY:
            self.profile = convert_identity_profile_to_float(profile)
        else:
            self.profile = profile
