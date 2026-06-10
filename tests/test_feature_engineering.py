import pytest
import numpy as np
import pandas as pd
from ml_engine.feature_engineering import extractor_to_model_features, FEATURE_COLUMNS, EXTRACTOR_TO_CICIDS

def test_feature_mapping_correctness():
    """Ensure the extractor features are correctly mapped to the model's expected 11 features."""
    
    # Mock data from the extractor
    extractor_data = {
        "src_ip": "1.2.3.4",
        "protocol": "TCP",
        "bytes_per_sec": "1500.5",
        "packets_per_sec": "10.0",
        "avg_packet_size": "150.05",
        "flow_duration": "2.5",
        "packet_count": "25",
        "total_bytes": "3751.25",
        "fwd_pkt_len_mean": "150.05",
        "fwd_pkt_len_std": "10.5",
        "flow_iat_mean": "0.1",
        "flow_iat_std": "0.05",
        "small_packet_ratio": "0.2"
    }
    
    # Run the mapping function
    features_df = extractor_to_model_features(extractor_data)
    
    # Assert it returns a DataFrame with the correct shape
    assert isinstance(features_df, pd.DataFrame)
    assert features_df.shape == (1, len(FEATURE_COLUMNS))
    
    # Verify the values are correctly placed in the exact order specified by FEATURE_COLUMNS
    expected_values = {
        "Flow Bytes/s": 1500.5,
        "Flow Packets/s": 10.0,
        "Avg Packet Size": 150.05,
        "Flow Duration": 2.5,
        "Total Fwd Packets": 25.0,
        "Total Length of Fwd Packets": 3751.25,
        "Fwd Packet Length Mean": 150.05,
        "Fwd Packet Length Std": 10.5,
        "Flow IAT Mean": 0.1,
        "Flow IAT Std": 0.05,
        "Small Packet Ratio": 0.2
    }
    
    for i, col_name in enumerate(FEATURE_COLUMNS):
        assert features_df.iloc[0, i] == expected_values[col_name]

def test_feature_mapping_missing_fields():
    """Ensure missing fields default to 0.0 without crashing."""
    extractor_data = {
        "src_ip": "1.2.3.4",
        "protocol": "TCP"
        # missing all numeric features
    }
    
    features_df = extractor_to_model_features(extractor_data)
    assert features_df.shape == (1, len(FEATURE_COLUMNS))
    assert (features_df.values[0] == 0.0).all()

def test_feature_mapping_invalid_types():
    """Ensure invalid types (e.g., strings that can't be parsed) default to 0.0."""
    extractor_data = {
        "src_ip": "1.2.3.4",
        "protocol": "TCP",
        "bytes_per_sec": "invalid_string",
        "packets_per_sec": "10.0"
    }
    
    features_df = extractor_to_model_features(extractor_data)
    
    # bytes_per_sec (Flow Bytes/s) should be 0.0 due to parse failure
    idx = FEATURE_COLUMNS.index("Flow Bytes/s")
    assert features_df.iloc[0, idx] == 0.0
    
    # packets_per_sec (Flow Packets/s) should still be 10.0
    idx_pps = FEATURE_COLUMNS.index("Flow Packets/s")
    assert features_df.iloc[0, idx_pps] == 10.0

