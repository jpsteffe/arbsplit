FROM busybox:1.36
COPY src/ /www
EXPOSE 8080
CMD ["sh", "-c", "httpd -f -p ${PORT:-8080} -h /www"]
