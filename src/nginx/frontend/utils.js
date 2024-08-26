function parseCookie(cookie) {
  return cookie.split(';').reduce((acc, item) => {
    const [key, value] = item.split('=');
    acc[key.trim()] = decodeURIComponent(value);
    return acc;
  }, {});
}

function deleteAllCookies() {
  document.cookie.split(';').forEach(cookie => {
      const eqPos = cookie.indexOf('=');
      const name = eqPos > -1 ? cookie.substring(0, eqPos) : cookie;
      document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT';
  });
}

/**
 * 
 * @param {*} name The name of the cookie
 * @param {*} value The value of the cookie
 * @param {*} expr The expiration date of the cookie in ms
 */
function setCookie(name, value, expr) {
  const d = new Date();
  d.setTime(d.getTime() + expr);
  document.cookie = `${name}=${value};expires=${d.toUTCString()}`;
}

async function fetchAPI(url, init) {
  const cookies = parseCookie(document.cookie);
  const headers = new Headers();
  headers.append('Content-Type', 'application/json');
  if (cookies.access_token) {
    headers.append('Authorization', `Bearer ${cookies.access_token}`);
  }
  const response = await fetch(url, { ...init, headers });
  return response;
}