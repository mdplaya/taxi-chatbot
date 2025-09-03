import pytest

# This legacy test targets a CSV+pandas-based data manager.
# The project has moved to an in-code catalog (utils.gcp_catalog).
# Skip this module to avoid pulling pandas into runtime tests.
pytest.skip("Legacy GCPDataManager tests skipped (replaced by in-code catalog).", allow_module_level=True)

import unittest
from unittest.mock import patch, MagicMock
import io
from utils.gcp_data_manager import GCPDataManager

class TestGCPDataManager(unittest.TestCase):

    def setUp(self):
        # Reset the singleton instance before each test
        GCPDataManager._instance = None

    @patch('pandas.read_csv')
    def test_singleton_pattern(self, mock_read_csv):
        instance1 = GCPDataManager()
        instance2 = GCPDataManager()
        self.assertIs(instance1, instance2)

    @patch('pandas.read_csv')
    def test_is_valid_machine_type(self, mock_read_csv):
        mock_csv_data = "name,description\nn1-standard-1,Test description"
        mock_df = pd.read_csv(io.StringIO(mock_csv_data))
        mock_read_csv.return_value = mock_df
        
        data_manager = GCPDataManager()
        self.assertTrue(data_manager.is_valid_machine_type('n1-standard-1'))
        self.assertFalse(data_manager.is_valid_machine_type('invalid-type'))

    @patch('pandas.read_csv')
    def test_is_valid_region(self, mock_read_csv):
        mock_csv_data = "region,supported_machine_types\nus-central1,n1-standard-1"
        mock_df = pd.read_csv(io.StringIO(mock_csv_data))
        mock_read_csv.return_value = mock_df

        data_manager = GCPDataManager()
        self.assertTrue(data_manager.is_valid_region('us-central1'))
        self.assertFalse(data_manager.is_valid_region('invalid-region'))

    @patch('pandas.read_csv')
    def test_is_machine_type_supported_in_region(self, mock_read_csv):
        mock_csv_data = "region,supported_machine_types\nus-central1,n1-standard-1 n2-standard-2"
        mock_df = pd.read_csv(io.StringIO(mock_csv_data))
        mock_read_csv.return_value = mock_df

        data_manager = GCPDataManager()
        self.assertTrue(data_manager.is_machine_type_supported_in_region('n1-standard-1', 'us-central1'))
        self.assertFalse(data_manager.is_machine_type_supported_in_region('n1-standard-4', 'us-central1'))
        self.assertFalse(data_manager.is_machine_type_supported_in_region('n1-standard-1', 'invalid-region'))

    @patch('pandas.read_csv')
    def test_get_all_machine_types(self, mock_read_csv):
        mock_csv_data = "name,description\nn1-standard-1,desc1\nn1-standard-2,desc2"
        mock_df = pd.read_csv(io.StringIO(mock_csv_data))
        mock_read_csv.return_value = mock_df

        data_manager = GCPDataManager()
        self.assertEqual(data_manager.get_all_machine_types(), ['n1-standard-1', 'n1-standard-2'])

if __name__ == '__main__':
    unittest.main()
