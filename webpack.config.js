/* eslint-env node */
const production = process.env.ENVIRONMENT !== "devel";

module.exports = {
  entry: {
    main: "./static/js/main.js",
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
