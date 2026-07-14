query Input {
  cart {
    lines {
      id
      quantity
      cost {
        amountPerQuantity {
          amount
          currencyCode
        }
        compareAtAmountPerQuantity {
          amount
          currencyCode
        }
      }
      merchandise {
        __typename
        ... on ProductVariant {
          id
          sku
          product {
            id
          }
        }
      }
    }
  }
  discount {
    metafield(namespace: "$app:compare-at-best-wins", key: "function-configuration") {
      jsonValue
    }
  }
}
