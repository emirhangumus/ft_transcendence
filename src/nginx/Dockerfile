FROM nginx:1.25

# Remove the default configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d

# Copy the SSL certificates
COPY ./certs/nginx-selfsigned.crt /etc/ssl/certs/nginx-selfsigned.crt
COPY ./certs/nginx-selfsigned.key /etc/ssl/private/nginx-selfsigned.key
COPY ./certs/dhparam.pem /etc/ssl/certs/dhparam.pem

# Copy the frontend files
COPY ./frontend /usr/share/nginx/html

# Expose ports for HTTP and HTTPS
EXPOSE 80 443
