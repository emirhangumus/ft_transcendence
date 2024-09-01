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

function parseRoutes(routes) {
  const transformedRoutes = {};
  Object.entries(routes).forEach(([path, config]) => {
    const variables = [];
    const transformedPath = path.replace(/([#:])(\w+)\((\d+)\)/g, (match, symbol, name, length) => {
      if (symbol === ':') {
        variables.push({ name, length: parseInt(length, 10) });
      }
      return `${symbol}${name}(${length})`;
    });

    transformedRoutes[path] = {
      endpoint: config.endpoint,
      variables: variables
    };
  });

  return transformedRoutes;
}

function getEndpoint(routes, path) {
  // Split the path into route path and query parameters
  const [routePath, queryString] = path.split('?');
  const queryParams = new URLSearchParams(queryString);

  for (const [routePattern, config] of Object.entries(routes)) {
      // Split the route pattern and path into parts
      const routeParts = routePattern.split('/').filter(Boolean);
      const pathParts = routePath.split('/').filter(Boolean);

      // Check if the path length matches the route length
      if (routeParts.length !== pathParts.length) continue;

      // Variables to hold matched values
      const variables = {};

      // Flag to check if the path matches the route pattern
      let isMatch = true;

      // Iterate over each part to check for match
      for (let i = 0; i < routeParts.length; i++) {
          const routePart = routeParts[i];
          const pathPart = pathParts[i];

          if (routePart.startsWith(':')) {
              // Extract variable name and constraints
              const [name, length] = routePart.slice(1).split('(');
              const variableLength = parseInt(length, 10);
              
              // Validate the length of the variable
              if (variableLength && pathPart.length !== variableLength) {
                  isMatch = false;
                  break;
              }

              // Store the variable
              variables[name] = pathPart;
          } else if (routePart !== pathPart) {
              isMatch = false;
              break;
          }
      }

      if (isMatch) {
          // Check if the config includes query parameters and validate them
          if (config.queryParams) {
              for (const [key, value] of Object.entries(config.queryParams)) {
                  if (queryParams.get(key) !== value) {
                      isMatch = false;
                      break;
                  }
              }
          }

          if (isMatch) {
              // Replace variables in the endpoint with actual values
              let endpoint = config.endpoint;
              Object.keys(variables).forEach(name => {
                  endpoint = endpoint.replace(`:${name}`, variables[name]);
              });

              return endpoint;
          }
      }
  }

  // Return false if no match is found
  return false;
}
