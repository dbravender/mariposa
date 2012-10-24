-- intentionally making this imperfect so it can be migrated
CREATE TABLE users (
  id int PRIMARY KEY,
  name varchar(255),
  password_sha1 varchar(40)
);