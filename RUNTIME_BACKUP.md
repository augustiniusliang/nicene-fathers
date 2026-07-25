# Runtime cache backup

This repository preserves the completed LaTeX collection together with the
non-secret runtime data needed to inspect or resume the translation job.

## Contents

- `work/<source-id>/source.json`: normalized source paragraphs.
- `work/<source-id>/translation.json`: completed translations.
- `work/collection/work_manifest.json`: collection manifest.
- `runtime-backup/jobs.sqlite3.gz.part-*`: gzip-compressed, split job database.
- `runtime-backup/jobs.sqlite3.sha256`: checksum of the restored database.
- `runtime-backup/token-usage-logs.tar.gz`: per-document usage logs.
- `runtime-backup/progress.log.gz` and `progress.jsonl.gz`: compressed progress logs.

Environment files, API/SMTP credentials, SSH keys, virtual environments, and
the deployment host configuration are intentionally excluded.

## Restore the job database

On Linux:

```sh
cat runtime-backup/jobs.sqlite3.gz.part-* | gzip -dc > jobs.sqlite3
sha256sum -c runtime-backup/jobs.sqlite3.sha256
```

## Restore logs

From the intended `work` directory:

```sh
tar -xzf ../runtime-backup/token-usage-logs.tar.gz
gzip -dc ../runtime-backup/progress.log.gz > collection/progress.log
gzip -dc ../runtime-backup/progress.jsonl.gz > collection/progress.jsonl
```
