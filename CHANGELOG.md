# Changelog

All notable changes to this project will be documented in this file.

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