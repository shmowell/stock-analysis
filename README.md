# Stock Recommendation Framework v2.0

A research-backed stock analysis system combining quantitative scoring with disciplined human judgment.

## Overview

This framework implements a **Model-First** approach to stock recommendations:
1. Calculate objective scores using evidence-based methodologies
2. Display base model recommendations
3. Allow documented human overrides when you see something the model doesn't

## Key Features

- **Percentile-Based Scoring**: Ranks stocks within your universe, robust to outliers
- **Three-Pillar Analysis**:
  - Fundamental (45%): Value, Quality, Growth
  - Technical (35%): Momentum, Trend, Volume patterns
  - Sentiment (20%): Market & stock-specific indicators
- **Override System**: Systematic approach to applying human judgment
- **Performance Tracking**: Quarterly reviews to measure override effectiveness

## Project Status

🚧 **Phase 1: Foundation** (In Progress)
- ✅ Project structure created
- ✅ Development guidelines established (CLAUDE.md)
- ⏳ API integration setup
- ⏳ Data collection infrastructure

See [CLAUDE.md](CLAUDE.md) for complete development guidelines.

## Directory Structure

```
stock-analysis/
├── src/                    # Source code
│   ├── data_collection/    # API integrations
│   ├── calculators/        # Scoring logic
│   ├── models/            # Composite models
│   └── utils/             # Helper functions
├── data/                  # Data storage
│   ├── raw/              # Original API responses
│   └── processed/        # Calculated scores
├── logs/                  # Logging and tracking
│   ├── overrides/        # Override documentation
│   └── quarterly_reviews/ # Performance reviews
├── config/               # Configuration files
├── templates/            # Documentation templates
├── tests/                # Unit and integration tests
└── docs/                 # Additional documentation
```

## Quick Start

### Prerequisites

- Python 3.9+
- API Keys (see Setup section)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/shmowell/stock-analysis.git
   cd stock-analysis
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure API keys:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Review the methodology:
   - Read `Stock_Recommendation_Framework_v2_Research_Enhanced.md`
   - Review development guidelines in `CLAUDE.md`

## Development

### Workflow

1. Read relevant section in framework document
2. Follow spec-driven development (CLAUDE.md)
3. Write tests first
4. Implement feature
5. Document and commit

### Key Principles

- **Percentile ranking, not linear scoring**
- **Model-first, override second**
- **Always document overrides**
- **Research-backed weights (45/35/20)**

See [CLAUDE.md](CLAUDE.md) for complete development standards.

## Research Foundation

Based on academic research from:
- Fama & French: Factor models
- Jegadeesh & Titman: Momentum effects
- Baker & Wurgler: Sentiment analysis
- Gu, Kelly & Xiu: Machine learning in asset pricing

See Framework Appendix C for complete citations.

## License

[Add license information]

## Contributing

Please read [CLAUDE.md](CLAUDE.md) for development guidelines and coding standards.

## Contact

[Add contact information]
