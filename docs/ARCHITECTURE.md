# Architecture

## Separation

- Client mobile (Flutter): customer journey (scan, cart, checkout)
- Employee web: management and monitoring
- Shared API backend: model inference + business endpoints

## Data and ML assets

- `ml/models/model_1`: product AI pipeline assets
- `ml/models/model_2`: meat freshness classifier assets
- `ml/notebooks`: experiments and training notebooks
- `data/*`: datasets and generated artifacts

## Runtime flow

1. Mobile/Web uploads image
2. Backend runs corresponding model
3. Backend returns prediction payload
4. Frontend displays result and actions by role

