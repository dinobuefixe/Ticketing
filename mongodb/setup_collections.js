// Cria (ou atualiza) as coleções do projeto com validadores e índices.
// Corre-se como root, via stdin, a partir de scripts/setup.sh. Pode ser repetido sem erro.
// Usa process.env.DB para saber a base de dados.

const d = db.getSiblingDB(process.env.DB);

// Registo de tentativas de hold (Parte 1). Cada tentativa é um documento, sucesso ou recusa.
const holdAttemptsName = "hold_attempts";
const holdAttemptsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["customer_id", "performance_id", "requested", "result", "attempted_at"],
    properties: {
      customer_id:    { bsonType: "string", description: "UUID do cliente" },
      performance_id: { bsonType: "string", description: "UUID da performance" },
      requested:      { bsonType: "object", description: "lugares ou número de lugares pedidos" },
      result:         { enum: ["accepted", "refused"] },
      reason:         { bsonType: ["string", "null"] },
      attempted_at:   { bsonType: "date" }
    }
  }
};
const strict = { validator: holdAttemptsValidator, validationLevel: "strict", validationAction: "error" };

if (d.getCollectionNames().includes(holdAttemptsName)) {
  d.runCommand({ collMod: holdAttemptsName, ...strict });
  print("coleção atualizada: " + holdAttemptsName);
} else {
  d.createCollection(holdAttemptsName, strict);
  print("coleção criada: " + holdAttemptsName);
}

// TTL de 90 dias: o MongoDB apaga os documentos sozinho
d.getCollection(holdAttemptsName).createIndex(
  { attempted_at: 1 },
  { name: "attempted_at_ttl", expireAfterSeconds: 90 * 24 * 60 * 60 }
);
d.getCollection(holdAttemptsName).createIndex(
  { performance_id: 1, attempted_at: -1 },
  { name: "performance_attempted_at" }
);
print("índices prontos em " + holdAttemptsName);