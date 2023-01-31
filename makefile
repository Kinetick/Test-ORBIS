build:
	docker build -t your_repo/app:test .

run:
	docker volume create test_app_files && \
	docker volume create test_app_db && \
	docker run \
	-dp 80:5000 \
	--name test_app \
	-v test_app_files:/app/files/ \
	-v test_app_db:/app/database/ \
	your_repo/app:test

stop:
	docker stop test_app

start:
	docker start test_app
