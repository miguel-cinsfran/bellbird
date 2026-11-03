const TOKEN_URL = "https://api.restream.io/oauth/token";
const MAXIMO_CAMPO = 512;
const MAXIMO_CUERPO = 4096;
const CAMPOS_RESPUESTA = [
  "access_token",
  "accessToken",
  "refresh_token",
  "refreshToken",
  "expires_in",
  "accessTokenExpiresIn",
  "accessTokenExpiresEpoch",
  "token_type",
  "scope",
];
const ERRORES_CONOCIDOS = new Set([
  "invalid_grant",
  "invalid_request",
  "invalid_client",
  "unauthorized_client",
  "unsupported_grant_type",
]);

function responder(cuerpo, estado) {
  // La respuesta puede traer tokens: ningún intermediario debe guardarla.
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function fallo(estado, codigo) {
  return responder({ error: codigo }, estado);
}

function esTexto(valor) {
  return typeof valor === "string" && valor.length > 0 && valor.length <= MAXIMO_CAMPO;
}

async function leerJson(request) {
  // El tope es en bytes: contar caracteres dejaría pasar un cuerpo con
  // acentos o emojis por encima del límite.
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.length > MAXIMO_CUERPO) {
    return null;
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

function destinos(env) {
  return String(env.REDIRECTS || "")
    .split(",")
    .map((destino) => destino.trim());
}

function formularioDe(ruta, datos, env) {
  if (ruta === "/exchange") {
    if (!esTexto(datos.code) || !esTexto(datos.redirect_uri)) {
      return null;
    }
    if (!destinos(env).includes(datos.redirect_uri)) {
      return null;
    }
    return new URLSearchParams({
      grant_type: "authorization_code",
      code: datos.code,
      redirect_uri: datos.redirect_uri,
    });
  }
  if (!esTexto(datos.refresh_token)) {
    return null;
  }
  return new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: datos.refresh_token,
  });
}

async function leerRespuesta(respuesta) {
  try {
    return await respuesta.json();
  } catch {
    return null;
  }
}

function filtrar(datos) {
  const salida = {};
  if (!datos || typeof datos !== "object") {
    return salida;
  }
  for (const campo of CAMPOS_RESPUESTA) {
    if (Object.prototype.hasOwnProperty.call(datos, campo)) {
      salida[campo] = datos[campo];
    }
  }
  return salida;
}

function codigoDeError(datos) {
  // La documentación describe `error` como texto, pero medido el 03/11/2026
  // Restream manda un objeto y el nombre queda en `error.name`, por ejemplo
  // {"statusCode":400,...,"name":"invalid_grant"}.
  const error = datos && typeof datos === "object" ? datos.error : undefined;
  let codigo;
  if (typeof error === "string") {
    codigo = error;
  } else if (error && typeof error === "object") {
    codigo = error.name;
  }
  return typeof codigo === "string" && ERRORES_CONOCIDOS.has(codigo)
    ? codigo
    : "server_error";
}

async function atender(request, env) {
  const ruta = new URL(request.url).pathname;
  if (request.method !== "POST" || (ruta !== "/exchange" && ruta !== "/refresh")) {
    return fallo(404, "not_found");
  }
  if (env.LIMITE) {
    const ip = request.headers.get("CF-Connecting-IP") || "";
    const resultado = await env.LIMITE.limit({ key: ip });
    if (resultado && resultado.success === false) {
      return fallo(429, "rate_limited");
    }
  }
  const datos = await leerJson(request);
  if (!datos || typeof datos !== "object" || Array.isArray(datos)) {
    return fallo(400, "invalid_request");
  }
  const formulario = formularioDe(ruta, datos, env);
  if (!formulario) {
    return fallo(400, "invalid_request");
  }

  let respuestaRestream;
  try {
    respuestaRestream = await fetch(TOKEN_URL, {
      method: "POST",
      headers: {
        Authorization: `Basic ${btoa(`${env.CLIENT_ID}:${env.CLIENT_SECRET}`)}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formulario,
    });
  } catch {
    return fallo(502, "server_error");
  }

  const cuerpo = await leerRespuesta(respuestaRestream);
  if (respuestaRestream.status === 200) {
    return responder(filtrar(cuerpo), 200);
  }
  return fallo(respuestaRestream.status, codigoDeError(cuerpo));
}

export default {
  async fetch(request, env) {
    return atender(request, env);
  },
};
