# Changelog

All notable changes to napari-isolate-cell will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2025-08-15
### Fixed
- Fixed reader registration issue when installed via pip
- Added priority to TIFF reader to override napari's default reader
- Improved path resolution for output files
- Added fallback to home directory when source path cannot be determined
- Store source path in layer metadata for better path tracking

### Changed
- Output files now save to user's home directory in 'napari_isolated_outputs' when source path is unknown
- Added support for uppercase TIFF extensions (.TIF, .TIFF)

## [0.1.1] - 2025-08-06
### Added
- Initial working release with improved build configuration

## [0.1.0] - 2024-12-01
### Added
- Initial release
- Click-based cell isolation from dense segmentations
- Automatic TIFF scale detection (standard and ImageJ metadata)
- SWC file export with proper physical coordinates
- Morphological closing for fragmented segmentations
- Support for anisotropic voxel spacing
- napari widget with interactive interface