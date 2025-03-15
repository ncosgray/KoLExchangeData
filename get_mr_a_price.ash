void main()
{
    // Get lowest mall price for Mr. A
    item mr_a = $item[ Mr. Accessory ];
    int price = mall_price(mr_a);
    int rate = price / 10;
    
    // Figure out what the current IOTM is
    string iotm_id = 0;
    string iotm_name = "";
    string iotm_type = "";
    string mr_store = visit_url("mrstore.php", false);
    string match_pattern = "(?s)-of-the-Month<\\/b>.*?<img.*?onclick='descitem\\((\\d+)\\)' alt=\"([^\"]+)\"";
    matcher match_iotm = create_matcher(match_pattern, mr_store);
    if (match_iotm.find()) {
      iotm_id = match_iotm.group(1);
      iotm_name = match_iotm.group(2);
    }

    // Get the IOTM type
    boolean iotm_is_familiar = false;
    string iotm_page = visit_url(`desc_item.php?whichitem={iotm_id}`, false);
    string familiar_pattern = "Hatches into:";
    matcher match_familiar = create_matcher(familiar_pattern, iotm_page);
    if (match_familiar.find()) {
      iotm_is_familiar = true;
    }

    // Date strings
    string game_date = today_to_string();
    string now = now_to_string("yyyy-MM-dd HH:mm:ss");
    
    // Dump the data to stdout
    print( `\{ \"mall_price\": {price}, \"rate\": {rate}, \"iotm_id\": {iotm_id}, \"iotm_name\": \"{iotm_name}\", \"iotm_is_familiar\": {iotm_is_familiar}, \"game_date\": \"{game_date}\", \"now": \"{now}\" \}` );
}
