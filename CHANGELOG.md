# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.5.0] - 2025-03-23

### Changed
- Completely inverted the risk management approach to be more intuitive:
  - Stoploss values are now the primary parameters (min_stoploss, max_stoploss)
  - ROI targets are derived from stoploss values using risk-reward ratio
  - Risk-reward ratio now properly represents reward:risk (e.g., 1:2 means target 2x profit relative to risk)
- Refactored risk management components to reduce dependencies:
  - StoplossCalculator now depends only on config
  - ROICalculator depends only on config
  - Strategy class coordinates between components
- Updated test suite to verify new risk management approach:
  - Rewrote test_calculate_dynamic_stoploss using parameterized tests
  - Added test for ROI calculation from stoploss values
  - Updated config tests to verify stoploss-to-ROI relationship
  - Enhanced test for strategy exit behavior with different regimes

### Fixed
- Made win rate scaling behavior more logical - higher win rates now use wider stoploss (more negative)
- Fixed risk-reward ratio calculation to properly convert between stoploss and ROI
- Improved boundary handling for stoploss and ROI values
- Fixed configuration parameter handling for min/max stoploss values
- Fixed trade cache ID handling in tests for more reliable test execution
- Resolved issues with test patching for better reproducibility
- Separated stoploss ordering test from other logical consistency tests

### Technical
- Reduced component coupling for better maintainability
- Improved separation of concerns in risk management system
- Enhanced testability of individual components
- Improved test stability with consistent datetime/timestamp handling
- Added more comprehensive test assertions for derived parameters
- Added parameterized tests for all market regimes and trade directions
- Better debug output in failing tests for easier troubleshooting
- Improved handling of floating-point comparisons in tests

## [0.4.0] - 2025-03-22

### Added
- Add automatic timeframe detection from FreqTrade configuration
- Add simplified system to use optimal parameters for each timeframe

### Changed
- Simplify timeframe configuration handling with direct string values
- Improve strategy initialization with auto-detection capabilities
- Update README with latest features and documentation

### Fixed
- Fix timeframe auto-detection edge cases
- Fix compatibility with test suite for timeframe detection
- Fix configuration loading for various timeframes

## [0.3.0] - 2025-03-22

### Added
- Add setup-strategy.sh installation script
- Add Git hooks for automatic strategy updates on pull/checkout
- Add sample strategy wrapper for easier FreqTrade integration

### Changed
- Restructure root directories for better organization
- Use relative imports for implementation files
- Refactor package references for Python package mode
- Refactor directory structure again for better maintainability
- Simplify Git hook for copying strategy into FreqTrade

### Improved
- Refactor and expand integration tests
- Fix mocking issues in conftest

## [0.2.0] - 2025-03-19

### Added
- Add README documentation (d5c9f68)

### Improved
- Make 30m strategy profitable
- Make 15m strategy more profitable (9162a52)
- Make 15m strategy profitable (6de9fbd)
- Make 5m strategy profitable (521c49b)
- 5m parameters optimization (42496c5)

### Fixed
- Fix config loading and error handling for bad loading (e228cf2)
- Fix minimal ROI dictionary (264963b)
- Fix import in strategy config (fd7f962)
- Fix backstop stoploss and take profit (bc4d768)
- Fix direction in trade entry (fc641fd)
- Fix performance tracker not clearing on backtest reload (bf92776)
- Fix performance data clearing for backtesting (434fa47)
- Fix clamping in stoploss calculation test (3ebd36c)
- Fix tests after adding config validator (c67fa6a)
- Fix all tests after config refactor (5013a41)

### Changed
- Remove default stoploss and ROI, add dynamic values to init (f540236)
- Integrate config validation (5b3d975)
- Config simplification (work in progress) (2f18fd1)
- De-leverage profit before comparison (b762f0f)
- Combine custom_stoploss and should_exit to prevent conflict (33adaae)
- Reset stoploss to config value (6e6954e)
- Optimize code base (d58bdae)
- Refactor integration tests (cd166af)
- Remove remaining ignored files and debugging test (69b37b1)
- Remove pycache from repo, add stoploss integration test (21cf295)
- Use direct imports instead of module (000a254)
- Refactor logging system (7d18170)
- Refactor directory structure for relative imports (590807e)
- Relative imports and poetry setup (77aa1c3)

### Other
- Changes (unspecified) (1e865db)
- Broken changes to stoploss calculation (c3f8b7f)
- Fix tests (498d796)
- Initial commit (8027976)
- Improve tests and validation (work in progress) (0aab8d9)

## [0.1.0] - 2025-03-17
- Initial project setup