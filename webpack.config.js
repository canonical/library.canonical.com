/* eslint-env node */

const production = process.env.ENVIRONMENT !== "devel";


module.exports = {
  entry: {
    "global-nav": "./static/js/global-nav.js",
    "cookie-policy": "./static/js/cookie-policy.js",
  },
  output: {
    filename: "[name].js",
    path: __dirname + "/static/js/build",
  },
  mode: production ? "production" : "development",
  devtool: production ? "source-map" : "eval-source-map",
  module: {
    rules: [
      {
        test: /\.js$/,
        // Exclude node_modules from using babel-loader
        // except some that use ES6 modules and need to be transpiled:
        // such as swiper http://idangero.us/swiper/get-started/
        // and also react-dnd related
        exclude: /node_modules\/(?!(dom7|ssr-window)\/).*/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["@babel/preset-env"],
          },
        },
      },
    ],
  },
  optimization: {
    minimize: true,
  },
};
