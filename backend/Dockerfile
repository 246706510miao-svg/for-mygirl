FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app/backend
COPY backend/pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY backend/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/backend/target/backend-0.1.0.jar /app/backend.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/backend.jar"]
