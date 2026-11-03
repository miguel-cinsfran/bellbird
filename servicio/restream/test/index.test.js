import { test } from "node:test";
import assert from "node:assert/strict";

import worker from "../src/index.js";

const CLIENT_ID = "cliente-de-prueba";
const CLIENT_SECRET = "secreto-de-prueba";
const REDIRECTS = [
  "http://localhost:47615/callback",
  "http://127.0.0.1:47615/callback",
  "http://localhost:47616/callback",
  "http://127.0.0.1:47616/callback",
].join(",");
const REDIRECT = "http://localhost:47615/callback";
const IP = "203.0.113.7";

function entorno(extra = {}) {
  return { CLIENT_ID, CLIENT_SECRET, REDIRECTS, ...extra };
}

function pedido(ruta, cuerpo, { metodo = "POST", cabeceras = {} } = {}) {
  const opciones = {
    method: metodo,
    headers: {
      "Content-Type": "application/json",
      "CF-Connecting-IP": IP,
      ...cabeceras,
    },
  };
  if (metodo !== "GET" && metodo !== "HEAD") {
    opciones.body = typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo);
  }
  return new Request(
    `https://restream-tokens.bellbird.workers.dev${ruta}`,
    opciones,
  );
}

function interceptar(t, { estado = 200, cuerpo = {} } = {}) {
  const original = globalThis.fetch;
  const llamadas = [];
  globalThis.fetch = async (url, opciones) => {
    llamadas.push({ url, opciones });
    return new Response(JSON.stringify(cuerpo), {
      status: estado,
      headers: { "Content-Type": "application/json" },
    });
  };
  t.after(() => {
    globalThis.fetch = original;
  });
  return llamadas;
}

function interceptarFallo(t, fallo) {
  const original = globalThis.fetch;
  const llamadas = [];
  globalThis.fetch = async (url, opciones) => {
    llamadas.push({ url, opciones });
    throw fallo;
  };
  t.after(() => {
    globalThis.fetch = original;
  });
  return llamadas;
}

function camposFormulario(opciones) {
  return Object.fromEntries(new URLSearchParams(opciones.body));
}

test("solo responde a POST en /exchange y /refresh", async (t) => {
  const llamadas = interceptar(t);
  const casos = [
    pedido("/otra", {}),
    pedido("/", {}),
    pedido("/exchange", {}, { metodo: "GET" }),
    pedido("/refresh", {}, { metodo: "PUT" }),
  ];
  for (const caso of casos) {
    const respuesta = await worker.fetch(caso, entorno());
    assert.equal(respuesta.status, 404);
    assert.deepEqual(await respuesta.json(), { error: "not_found" });
    assert.equal(respuesta.headers.get("content-type"), "application/json");
    assert.equal(respuesta.headers.get("cache-control"), "no-store");
  }
  assert.equal(llamadas.length, 0);
});

test("valida los campos, sus longitudes y el tamaño del cuerpo", async (t) => {
  const llamadas = interceptar(t);
  const invalidos = [
    ["/exchange", { redirect_uri: REDIRECT }],
    ["/exchange", { code: 123, redirect_uri: REDIRECT }],
    ["/exchange", { code: "codigo", redirect_uri: 5 }],
    ["/exchange", { code: "x".repeat(513), redirect_uri: REDIRECT }],
    ["/exchange", { code: "codigo", redirect_uri: "http://otro.example/callback" }],
    ["/refresh", {}],
    ["/refresh", { refresh_token: 42 }],
    ["/refresh", { refresh_token: "x".repeat(513) }],
  ];
  for (const [ruta, cuerpo] of invalidos) {
    const respuesta = await worker.fetch(pedido(ruta, cuerpo), entorno());
    assert.equal(respuesta.status, 400);
    assert.deepEqual(await respuesta.json(), { error: "invalid_request" });
  }
  assert.equal(llamadas.length, 0);

  const grande = JSON.stringify({
    code: "codigo",
    redirect_uri: REDIRECT,
    relleno: "a".repeat(5000),
  });
  assert.ok(new TextEncoder().encode(grande).length > 4096);
  let respuesta = await worker.fetch(pedido("/exchange", grande), entorno());
  assert.equal(respuesta.status, 400);
  assert.deepEqual(await respuesta.json(), { error: "invalid_request" });

  respuesta = await worker.fetch(pedido("/exchange", "{no es json"), entorno());
  assert.equal(respuesta.status, 400);
  assert.deepEqual(await respuesta.json(), { error: "invalid_request" });
  assert.equal(llamadas.length, 0);

  for (const redireccion of REDIRECTS.split(",")) {
    respuesta = await worker.fetch(
      pedido("/exchange", { code: "codigo", redirect_uri: redireccion }),
      entorno(),
    );
    assert.equal(respuesta.status, 200);
  }
  assert.equal(llamadas.length, 4);
});

test("el client_id sale de la configuración y no del pedido", async (t) => {
  const llamadas = interceptar(t, { cuerpo: { access_token: "acceso" } });
  const respuesta = await worker.fetch(
    pedido("/exchange", {
      code: "codigo",
      redirect_uri: REDIRECT,
      client_id: "cliente-falso",
    }),
    entorno(),
  );
  assert.equal(respuesta.status, 200);
  const { opciones } = llamadas[0];
  assert.equal(
    opciones.headers.Authorization,
    `Basic ${btoa(`${CLIENT_ID}:${CLIENT_SECRET}`)}`,
  );
  assert.equal(camposFormulario(opciones).client_id, undefined);
});

test("reenvía el formulario y la autenticación básica", async (t) => {
  const llamadas = interceptar(t, { cuerpo: { access_token: "acceso" } });
  await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  await worker.fetch(
    pedido("/refresh", { refresh_token: "renovacion" }),
    entorno(),
  );

  assert.equal(llamadas.length, 2);
  for (const llamada of llamadas) {
    assert.equal(llamada.url, "https://api.restream.io/oauth/token");
    assert.equal(llamada.opciones.method, "POST");
    assert.equal(
      llamada.opciones.headers.Authorization,
      `Basic ${btoa(`${CLIENT_ID}:${CLIENT_SECRET}`)}`,
    );
    assert.equal(
      llamada.opciones.headers["Content-Type"],
      "application/x-www-form-urlencoded",
    );
  }
  assert.deepEqual(camposFormulario(llamadas[0].opciones), {
    grant_type: "authorization_code",
    code: "codigo",
    redirect_uri: REDIRECT,
  });
  assert.deepEqual(camposFormulario(llamadas[1].opciones), {
    grant_type: "refresh_token",
    refresh_token: "renovacion",
  });
});

test("devuelve solo los campos permitidos de una respuesta 200", async (t) => {
  const completa = {
    access_token: "acceso",
    accessToken: "acceso-camel",
    refresh_token: "renovacion",
    refreshToken: "renovacion-camel",
    expires_in: 3600,
    accessTokenExpiresIn: 3600,
    accessTokenExpiresEpoch: 1800000000,
    token_type: "Bearer",
    scope: "chat.read",
    extra: "no sale",
    user: { id: 1 },
  };
  interceptar(t, { cuerpo: completa });
  let respuesta = await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  assert.equal(respuesta.status, 200);
  const { extra, user, ...permitidos } = completa;
  assert.deepEqual(await respuesta.json(), permitidos);

  interceptar(t, { cuerpo: { access_token: "acceso" } });
  respuesta = await worker.fetch(
    pedido("/refresh", { refresh_token: "renovacion" }),
    entorno(),
  );
  assert.equal(respuesta.status, 200);
  assert.deepEqual(await respuesta.json(), { access_token: "acceso" });
});

test("traduce el error de Restream sin devolver su texto", async (t) => {
  interceptar(t, {
    estado: 400,
    cuerpo: { error: "invalid_grant", error_description: "texto interno" },
  });
  let respuesta = await worker.fetch(
    pedido("/refresh", { refresh_token: "renovacion" }),
    entorno(),
  );
  assert.equal(respuesta.status, 400);
  assert.deepEqual(await respuesta.json(), { error: "invalid_grant" });

  interceptar(t, {
    estado: 400,
    cuerpo: { error: "otra_cosa", error_description: "texto interno" },
  });
  respuesta = await worker.fetch(
    pedido("/refresh", { refresh_token: "renovacion" }),
    entorno(),
  );
  assert.equal(respuesta.status, 400);
  assert.deepEqual(await respuesta.json(), { error: "server_error" });

  interceptar(t, { estado: 401, cuerpo: { error: "invalid_client" } });
  respuesta = await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  assert.equal(respuesta.status, 401);
  assert.deepEqual(await respuesta.json(), { error: "invalid_client" });
});

test("responde 502 si no se puede hablar con Restream", async (t) => {
  interceptarFallo(t, new TypeError("sin red"));
  const respuesta = await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  assert.equal(respuesta.status, 502);
  assert.deepEqual(await respuesta.json(), { error: "server_error" });
});

test("consulta el límite con la IP y corta con 429", async (t) => {
  const llamadas = interceptar(t, { cuerpo: { access_token: "acceso" } });
  const claves = [];
  const limite = {
    async limit({ key }) {
      claves.push(key);
      return { success: false };
    },
  };
  for (const ruta of ["/exchange", "/refresh"]) {
    const cuerpoPedido =
      ruta === "/exchange"
        ? { code: "codigo", redirect_uri: REDIRECT }
        : { refresh_token: "renovacion" };
    const respuesta = await worker.fetch(
      pedido(ruta, cuerpoPedido),
      entorno({ LIMITE: limite }),
    );
    assert.equal(respuesta.status, 429);
    assert.deepEqual(await respuesta.json(), { error: "rate_limited" });
  }
  assert.deepEqual(claves, [IP, IP]);
  assert.equal(llamadas.length, 0);

  const permite = {
    async limit() {
      return { success: true };
    },
  };
  const permitido = await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno({ LIMITE: permite }),
  );
  assert.equal(permitido.status, 200);

  const sinLimite = await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  assert.equal(sinLimite.status, 200);
});

test("no escribe códigos, tokens ni el secreto", async (t) => {
  const llamadas = interceptar(t, {
    cuerpo: { access_token: "acceso-secreto", refresh_token: "renovacion-secreta" },
  });
  const registros = [];
  const originales = {
    log: console.log,
    error: console.error,
    warn: console.warn,
  };
  console.log = (...argumentos) => {
    registros.push(argumentos);
  };
  console.error = (...argumentos) => {
    registros.push(argumentos);
  };
  console.warn = (...argumentos) => {
    registros.push(argumentos);
  };
  t.after(() => {
    console.log = originales.log;
    console.error = originales.error;
    console.warn = originales.warn;
  });

  await worker.fetch(
    pedido("/exchange", { code: "codigo", redirect_uri: REDIRECT }),
    entorno(),
  );
  await worker.fetch(
    pedido("/refresh", { refresh_token: "renovacion" }),
    entorno(),
  );
  assert.equal(llamadas.length, 2);
  assert.deepEqual(registros, []);
});
