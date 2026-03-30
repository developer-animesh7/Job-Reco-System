# Backend Performance Notes

This project now uses batched ORM patterns in the resume analysis pipeline to reduce query count and improve throughput.

## Efficient Query Examples

### 1) Fetch many rows once with in_bulk

```python
jobs_by_title = Job.objects.filter(title__in=titles).in_bulk(field_name="title")
```

Why: avoids N queries for N titles.

### 2) Insert many rows in one statement

```python
Job.objects.bulk_create(new_jobs, ignore_conflicts=True)
```

Why: avoids repeated `get_or_create` insert calls in loops.

### 3) Update many rows at once

```python
Recommendation.objects.bulk_update(to_update, ["score"])
```

Why: reduces per-row update overhead.

### 4) Avoid N+1 on foreign keys

```python
Recommendation.objects.filter(resume=resume).select_related("job")
```

Why: joins `job` in a single query.

## ORM Best Practices

1. Prefer set-based operations over row-by-row operations.
2. Use `transaction.atomic()` for multi-step write flows.
3. Use `in_bulk`, `values`, and `values_list` for lightweight retrieval when full model instances are unnecessary.
4. Use `select_related` for ForeignKey and `prefetch_related` for reverse/many-to-many relations.
5. Keep filters narrow and indexed for high-cardinality fields.
6. Avoid calling `.save()` inside loops when bulk operations are possible.
7. Profile with Django Debug Toolbar or query logging before and after changes.

## File Handling Best Practices

1. Validate upload size before heavy processing.
2. Read only minimal bytes for signature checks.
3. Avoid loading full files in memory unless absolutely required.
4. Use Django's uploaded file handling (temporary files/chunks) instead of manual buffering.
5. Keep `FILE_UPLOAD_MAX_MEMORY_SIZE` low enough to push large files to temp storage.
