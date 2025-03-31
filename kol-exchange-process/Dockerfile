FROM public.ecr.aws/lambda/python:3.13

# Set working directory
ARG FUNCTION_DIR="/app"

# matplotlib config
ENV MPLCONFIGDIR="/tmp"

# Copy script files
RUN mkdir -p ${FUNCTION_DIR}
COPY . ${FUNCTION_DIR}
WORKDIR ${FUNCTION_DIR}

# Script dependencies
RUN dnf -y install shadow-utils
RUN pip install --no-cache-dir dynamo_pandas pandas matplotlib
RUN pip install --target ${FUNCTION_DIR} awslambdaric

# Change to nonroot user
RUN /usr/sbin/adduser nonroot
USER nonroot

# Set Lambda runtime interface client as default command
ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "app.handler" ]
