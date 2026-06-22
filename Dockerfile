FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY models.py .
COPY pipeline.py .
COPY lambda_function.py .
COPY services/ ./services/

CMD [ "lambda_function.lambda_handler" ]