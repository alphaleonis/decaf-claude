# Coverage Configuration

Expected format for the `## Coverage` section in a project's CLAUDE.md.

## Required Fields

```markdown
## Coverage
- **Command**: `<shell command to run coverage>`
- **Format**: cobertura | lcov | clover
- **Report path**: `<glob pattern to find report file(s)>`
- **Thresholds**: <N>% line, <N>% branch
```

| Field | Required | Description |
|-------|----------|-------------|
| Command | Yes | Shell command that runs tests with coverage collection |
| Format | Yes | Report format: `cobertura`, `lcov`, or `clover` |
| Report path | Yes | Glob pattern to locate the generated report file(s) |
| Thresholds | Yes | Minimum acceptable line and branch coverage percentages |

## Supported Report Formats

### Cobertura XML

XML format with `<package>` -> `<class>` -> `<line>` hierarchy. Common with .NET/Coverlet, Python/pytest-cov, Java/JaCoCo (cobertura output).

**Key elements:**
- `<package>` with `line-rate`, `branch-rate` attributes
- `<class>` with `filename`, `line-rate`, `branch-rate`
- `<line>` with `number`, `hits`, `branch`, `condition-coverage`

### LCOV

Line-oriented text format. Common with JS/c8, C/gcov, Go/gocov.

**Key records:**
- `SF:<filename>` — source file path
- `DA:<line>,<hits>` — line coverage data
- `BRDA:<line>,<block>,<branch>,<hits>` — branch coverage data
- `LF:<count>` / `LH:<count>` — lines found / lines hit
- `BRF:<count>` / `BRH:<count>` — branches found / branches hit

### Clover XML

XML format with `<file>` -> `<line>` hierarchy. Common with PHP/PHPUnit, Java/Clover.

**Key elements:**
- `<file>` with `name` attribute
- `<line>` with `num`, `type` (stmt/cond/method), `count`
- `<metrics>` with `statements`, `coveredstatements`, `conditionals`, `coveredconditionals`

## Example Configurations

### .NET with Coverlet

```markdown
## Coverage
- **Command**: `dotnet test --collect:"XPlat Code Coverage" --results-directory ./coverage`
- **Format**: cobertura
- **Report path**: `coverage/**/coverage.cobertura.xml`
- **Thresholds**: 80% line, 70% branch
```

### JavaScript/TypeScript with c8

```markdown
## Coverage
- **Command**: `npx c8 --reporter=lcov npm test`
- **Format**: lcov
- **Report path**: `coverage/lcov.info`
- **Thresholds**: 80% line, 75% branch
```

### Python with pytest-cov

```markdown
## Coverage
- **Command**: `pytest --cov=src --cov-report=xml:coverage.xml`
- **Format**: cobertura
- **Report path**: `coverage.xml`
- **Thresholds**: 85% line, 75% branch
```

### Java with JaCoCo (Cobertura output)

```markdown
## Coverage
- **Command**: `mvn test jacoco:report`
- **Format**: cobertura
- **Report path**: `target/site/jacoco/jacoco.xml`
- **Thresholds**: 80% line, 70% branch
```

### Go with gocov

```markdown
## Coverage
- **Command**: `go test -coverprofile=coverage.out ./... && gocov convert coverage.out > coverage.json && gocov-xml < coverage.json > coverage.xml`
- **Format**: cobertura
- **Report path**: `coverage.xml`
- **Thresholds**: 75% line, 65% branch
```

### PHP with PHPUnit

```markdown
## Coverage
- **Command**: `php vendor/bin/phpunit --coverage-clover coverage.xml`
- **Format**: clover
- **Report path**: `coverage.xml`
- **Thresholds**: 80% line, 70% branch
```

## Threshold Defaults

If a project specifies only line thresholds, apply these defaults for branch coverage:

| Line Threshold | Default Branch Threshold |
|---------------|------------------------|
| >= 90% | 80% |
| >= 80% | 70% |
| >= 70% | 60% |
| < 70% | 50% |
