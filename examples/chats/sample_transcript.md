# Research Notes: Machine Learning Pipeline

User: Can you explain how our ML pipeline works?

Bot: The ML pipeline has four main stages. First, raw data is collected from our PostgreSQL database and stored in S3. Then, Dr. Lisa Wang's data processing scripts clean and normalize the data using Apache Spark. The processed data feeds into our TensorFlow models, which are trained on GPU clusters managed by our MLOps engineer Kevin Nguyen. Finally, model predictions are served through a FastAPI endpoint.

User: Who maintains the Spark processing scripts?

Bot: Dr. Lisa Wang is the lead data scientist responsible for the Spark processing pipeline. She wrote the initial ETL scripts and maintains them. She works closely with Kevin Nguyen to ensure the processed data is compatible with the training infrastructure. Dr. Wang joined the company from Stanford where she specialized in distributed computing.

User: What about model versioning?

Bot: Kevin Nguyen implemented MLflow for model versioning and experiment tracking. Each trained model gets a version tag and is stored in our model registry. We keep the last 10 versions for rollback purposes. Production models are deployed through ArgoCD to our Kubernetes cluster. The current production model is version 2.3.1, trained on 2 million samples.
