from strategy import MACDTrendAdaptiveStrategy


def test_strategy_import():
    """Test that the strategy class is correctly exported from the package"""
    assert MACDTrendAdaptiveStrategy is not None
    assert hasattr(MACDTrendAdaptiveStrategy, 'INTERFACE_VERSION')
    assert MACDTrendAdaptiveStrategy.INTERFACE_VERSION == 3
