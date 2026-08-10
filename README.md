# Mini E-commerce con Microservicios

Proyecto de aprendizaje enfocado en arquitectura de microservicios, construido con Vue.js, FastAPI y PostgreSQL. El objetivo principal no es el e-commerce en si, sino practicar los problemas reales de un sistema distribuido: bases de datos separadas por servicio, comunicacion sincrona y asincrona entre servicios, autenticacion centralizada, service discovery, observabilidad, y una integracion real con una pasarela de pago.

## Stack tecnologico

- **Frontend:** Vue.js
- **Backend:** FastAPI (Python)
- **Bases de datos:** PostgreSQL (una instancia independiente por microservicio)
- **Mensajeria:** RabbitMQ
- **Gateway:** Traefik
- **Service discovery:** Consul
- **Autenticacion:** OAuth 2.0 (Authorization Code + PKCE) y JWT
- **Pagos:** Stripe (modo test)
- **Observabilidad:** Prometheus, Loki + Promtail, Grafana, OpenTelemetry + Jaeger
- **Orquestacion local:** Docker Compose

## Arquitectura

```
Vue.js (SPA)
    |
API Gateway (Traefik + Consul)
    |
    +-- auth-service      (OAuth2 + JWT)
    +-- catalog-service   (productos, stock)
    +-- order-service     (orquesta la saga de la orden)
    +-- payment-service   (Stripe + webhooks)
            |
        RabbitMQ
            |
    notification-service  (consume eventos, envia notificaciones)
```

Cada microservicio es independiente: tiene su propio codigo, su propia base de datos PostgreSQL, y se comunica con los demas via HTTP (sincrono) o eventos en RabbitMQ (asincrono).

## Estructura del repositorio

```
.
├── services/
│   ├── auth-service/
│   ├── catalog-service/
│   ├── order-service/
│   ├── payment-service/
│   └── notification-service/
├── gateway/
├── frontend/
├── infra/
│   ├── docker-compose.yml
│   └── observability/
└── README.md
```

## Requisitos previos

- Python 3.14+
- Node.js 24+
- Docker y Docker Compose
- uv (gestor de paquetes de Python)
- Stripe CLI (para probar webhooks en local)

## Puesta en marcha

```bash
git clone <url-del-repositorio>
cd <nombre-del-repositorio>
docker compose -f infra/docker-compose.yml up --build
```

El frontend quedara disponible en `http://localhost:5173` y el API Gateway en `http://localhost:8080`.

Para probar los webhooks de Stripe en local:

```bash
stripe listen --forward-to localhost:8080/payment/webhook
```

## Roadmap del proyecto

- [ ] Fase 1: nucleo del dominio (catalog-service + order-service)
- [ ] Fase 2: autenticacion con OAuth2 + JWT
- [ ] Fase 3: API Gateway y service discovery
- [ ] Fase 4: pagos con Stripe (modo test)
- [ ] Fase 5: mensajeria asincrona y patron saga
- [ ] Fase 6: notificaciones
- [ ] Fase 7: observabilidad (metricas, logs, tracing)
- [ ] Fase 8: todo integrado en Docker Compose

## Licencia

MIT
