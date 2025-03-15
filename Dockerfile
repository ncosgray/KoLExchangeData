FROM amazoncorretto:21-alpine

# Set working directory
ARG FUNCTION_DIR="/app"

# Copy script files
RUN mkdir -p ${FUNCTION_DIR}
COPY . ${FUNCTION_DIR}
WORKDIR ${FUNCTION_DIR}

# Alpine and Python packages
RUN apk add --no-cache \
    # kolmafia script dependencies
    bash curl jq py3-boto3 py3-pip python3 wget zip \
    # Lambda dependencies
    autoconf automake binutils cmake elfutils-dev g++ gcc libtool make python3-dev
RUN pip install --target ${FUNCTION_DIR} awslambdaric

# Install kolmafia
RUN bash install_kolmafia.sh

# Change to nonroot user
RUN adduser -D nonroot
USER nonroot

# Set Lambda runtime interface client as default command
ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "app.handler" ]
