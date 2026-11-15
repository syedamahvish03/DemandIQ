# Dataset notes

The application currently starts with generated **synthetic demonstration data** so the dashboard can run before a real dataset is downloaded.

## Planned starter dataset

Store Item Demand Forecasting Challenge (Kaggle):
https://www.kaggle.com/competitions/demand-forecasting-kernels-only/data

The commonly used training file contains daily observations with columns date, store, item, sales.

The dataset is suitable for learning demand forecasting. It does not contain actual inventory-on-hand quantities or supplier lead times. Those values must not be inferred or presented as real facts; later inventory features will use clearly identified user inputs or illustrative assumptions.

## Local data policy

Keep downloaded/raw datasets out of Git unless their licence and repository size make redistribution appropriate. See .gitignore.
