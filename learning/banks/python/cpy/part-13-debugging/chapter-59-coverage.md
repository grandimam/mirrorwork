# Chapter 59: Code Coverage

## 59.1 Using coverage.py

```bash
# Install
pip install coverage

# Run with coverage
coverage run -m pytest tests/
coverage run script.py

# Generate report
coverage report
coverage html  # HTML report in htmlcov/
```

## 59.2 Coverage API

```python
import coverage

cov = coverage.Coverage()
cov.start()

# Your code here
import mymodule
mymodule.function()

cov.stop()
cov.save()

# Report
cov.report()
cov.html_report(directory='htmlcov')
```

## 59.3 Branch Coverage

```python
# .coveragerc
[run]
branch = True

# Tracks both line and branch coverage
# Reports which branches were/weren't taken
```

## Summary

- coverage.py tracks which lines execute
- Branch coverage tracks decision paths
- HTML reports visualize coverage

---

[Next: Logging Internals →](chapter-60-logging.md)
