# Storage Model and Company Workspaces

## Intended storage model

This repository tracks lightweight production logic and metadata:

- intake contracts
- compiler behavior
- pool-plan YAML
- provider settings
- brand metadata (logo, plans)

Large media should **not** be committed to git.

## Media roots and external drives

The app supports local or externally mounted media roots for footage storage.

- default local footage root: `input_videos/`
- users can point UI controls to another local path or mounted drive
- pool/factory media can live outside the repository as long as the root is accessible

Recommended approach:

- keep metadata/config in repo
- keep raw footage and generated media on local/external storage

## Managed company workspace paths

When you create a company workspace, the app provisions a consistent set of managed paths:

- `data/brands/<slug>/`
- `creative_scripts/<company>/`
- `input_videos/portrait/<company>/`
- `input_videos/landscape/<company>/`
- `output_videos/portrait/<company>/`
- `output_videos/landscape/<company>/`

And ensures pool-fill ingestion folders:

- `input_videos/portrait/<company>/_INBOX`
- `input_videos/portrait/<company>/factory`
- `input_videos/landscape/<company>/_INBOX`
- `input_videos/landscape/<company>/factory`

## Deletion safety

Deletion in UI only targets these known managed paths for the selected company.

- starter/template/shared paths are never deleted
- when managed files exist, exact company-name confirmation is required
- deletion is path-scoped, not broad recursive cleanup outside managed definitions
