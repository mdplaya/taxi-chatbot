import pandas as pd
import os

class GCPDataManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GCPDataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.gcp_machine_types_df = None
        self.gcp_regions_and_supported_machine_types_df = None
        self._load_data()

    def _load_data(self):
        try:
            # Assuming the script is run from the project root
            machine_types_path = os.path.join(os.getcwd(), 'gcp_machine_types.csv')
            regions_path = os.path.join(os.getcwd(), 'gcp_regions_and_supported_machine_types.csv')

            if os.path.exists(machine_types_path):
                self.gcp_machine_types_df = pd.read_csv(machine_types_path)
            else:
                print(f"Warning: {machine_types_path} not found.")

            if os.path.exists(regions_path):
                self.gcp_regions_and_supported_machine_types_df = pd.read_csv(regions_path)
            else:
                print(f"Warning: {regions_path} not found.")
        except Exception as e:
            print(f"Error loading GCP data: {e}")

    def is_valid_machine_type(self, machine_type: str) -> bool:
        if self.gcp_machine_types_df is not None:
            return machine_type in self.gcp_machine_types_df['name'].values
        return False

    def is_valid_region(self, region: str) -> bool:
        if self.gcp_regions_and_supported_machine_types_df is not None:
            return region in self.gcp_regions_and_supported_machine_types_df['region'].values
        return False

    def is_machine_type_supported_in_region(self, machine_type: str, region: str) -> bool:
        if self.gcp_regions_and_supported_machine_types_df is not None:
            region_df = self.gcp_regions_and_supported_machine_types_df[self.gcp_regions_and_supported_machine_types_df['region'] == region]
            if not region_df.empty:
                supported_machines = region_df['supported_machine_types'].iloc[0]
                return machine_type in supported_machines
        return False

    def get_all_machine_types(self) -> list[str]:
        if self.gcp_machine_types_df is not None:
            return self.gcp_machine_types_df['name'].tolist()
        return []
