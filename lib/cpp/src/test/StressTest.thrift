namespace test.stress

service Service {

  void echoVoid(),
  byte echoByte(byte arg),
  u16 echoU16(u16 arg),
  u32 echoU32(u32 arg),
  u64 echoU64(u64 arg),
  string echoString(string arg),
  list<byte>  echoList(list<byte> arg),
  set<byte>  echoSet(set<byte> arg),
  map<byte, byte>  echoMap(map<byte, byte> arg),
}
