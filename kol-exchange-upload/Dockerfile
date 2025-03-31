FROM public.ecr.aws/lambda/java:21

# Set working directory
ARG FUNCTION_DIR="/app"

# Copy script files
RUN mkdir -p ${FUNCTION_DIR}
COPY . ${FUNCTION_DIR}
WORKDIR ${FUNCTION_DIR}

# Script dependencies
RUN dnf -y install gzip jq tar python3 python3-boto3 shadow-utils wget
RUN pip install --target ${FUNCTION_DIR} awslambdaric

# Change to nonroot user
RUN /usr/sbin/adduser nonroot
USER nonroot

# Set Lambda runtime interface client as default command
ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "app.handler" ]
