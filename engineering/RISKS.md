# Risks

- **Technical Debt**: Rapid prototyping of testing scripts leads to fragmentation.
- **Single Points of Failure**: Local Redis instance. If it goes down, state is lost.
- **Deployment Risks**: Manual `.env` management could lead to desync across services.
- **Training Risks**: Overfitting on narrow datasets for specific languages.
