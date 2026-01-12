# gcloud storage rsync

Synchronize content between two buckets/directories (local ↔ GCS ↔ S3)

## Synopsis

```bash
gcloud storage rsync SOURCE DESTINATION
  [--recursive] [--delete-unmatched-destination-objects]
  [--dry-run] [--continue-on-error]
  [--exclude=REGEX,...] 
  [--include=REGEX,...]
  ....
```
## Description

`gcloud storage rsync` synchronizes objects so that **DESTINATION** matches **SOURCE**.

- Copies missing files
- Overwrites changed files
- Can delete extra files in destination (with `--delete-unmatched-destination-objects`)
- Does **not** copy empty directory trees (Cloud Storage uses flat namespace)

**Important note**  
For large cross-cloud transfers (e.g. GCS ↔ S3), running the command from a **Google Compute Engine VM** in the same region as one of the buckets is usually **significantly faster**.

## Common Examples

```bash /powershell
# Local → GCS
gcloud storage rsync ./data gs://my-bucket/data

# Local → GCS (recursive)
gcloud storage rsync ./data gs://my-bucket/data --recursive

# GCS → local (mirror, delete extras)
gcloud storage rsync gs://my-bucket/data ./my-local-data \
  --recursive --delete-unmatched-destination-objects

# GCS → GCS (mirror + delete)
gcloud storage rsync gs://source-bucket gs://dest-bucket \
  --recursive --delete-unmatched-destination-objects

# Cross-cloud (GCS → S3)
gcloud storage rsync gs://my-gs-bucket s3://my-s3-bucket \
  --recursive --delete-unmatched-destination-objects

# Dry run (very recommended before --delete!)
gcloud storage rsync gs://prod-backup gs://test-backup \
  --recursive --delete-unmatched-destination-objects --dry-run
```
## Most Frequently Used Flags

| Flag                                       | Meaning                                                                                   |
|--------------------------------------------|-------------------------------------------------------------------------------------------|
| `-r`, `--recursive`                        | Process directories recursively                                                           |
| `--delete-unmatched-destination-objects`   | **Delete** files in destination that don't exist in source (dangerous!)                  |
| `--dry-run`                                | Show what would happen without actually doing anything                                    |
| `--exclude="regex_pattern"`                | Skip files matching Python regex (can be repeated)                                        |
| `--no-clobber`, `-n`                       | Never overwrite existing destination files/objects                                        |
| `--checksums-only`                         | Compare using hashes only (ignore mtime)                                                  |
| `--skip-if-dest-has-newer-mtime`, `-u`     | Skip if destination is newer                                                              |
| `--gzip-in-flight=jpg,png,css,js`          | Compress these file types during transfer only (saves bandwidth)                          |
| `--gzip-in-flight-all`                     | Gzip **all** files during transfer (use carefully)                                        |
| `--continue-on-error`, `-c`                | Keep going after errors (sequential mode only)                                            |
| `--preserve-posix`, `-P`                   | Preserve POSIX attributes (mtime, atime, uid, gid, mode)                                  |

## Metadata & Encryption Related Flags

```bash
# Set / update metadata
--content-type="image/webp"
--cache-control="public, max-age=31536000"
--custom-metadata=env=prod,deployed=2025-01

# Clear all custom metadata (except POSIX if --preserve-posix is used)
--clear-custom-metadata

# Customer-supplied encryption
--encryption-key=base64AES256key...
--decryption-keys=key1,key2,key3
```
## Exclude / Include Patterns – Quick Reference

```bash
# Skip all .tmp and .log files
--exclude=".*\.(tmp|log)$"

# Skip everything in temp/ folders
--exclude=".*/temp/.*"

# Only include .jpg but skip anything in old/
--include=".*\.jpg$" --exclude=".*old/.*"

# Windows cmd.exe escaping note
--exclude=".*\.jpg$|.*\.tmp$"
```
## Safety Recommendations
1. Always test first with `--dry-run`
2. Use `--no-clobber` when you're not 100% sure
3. Consider `--checksums-only` for critical data
4. **Never** run `--delete-unmatched-destination-objects` without `--dry-run` first
5. For very large transfers → run from GCE VM in the same region

