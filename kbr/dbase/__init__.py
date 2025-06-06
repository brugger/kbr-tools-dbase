"""

Generica low level function for interacting with a database through the records package


"""


import re
import os
import pprint
pp = pprint.PrettyPrinter(indent=4)

import records

import kbr.type_utils as type_utils


class DB( object ):

    def __init__( self, uri:str, **kwargs) -> object:
        """ connects to a database instance 

        Args:
        url: as specified by sqlalchemy ( {driver}://{user}:{password}@{host}:{port}/{dbase}
        
        Returns:
        none
        
        Raises:
        RuntimeError on failure.


        """
    
        self._db = records.Database( uri, **kwargs )
        self._uri = uri
        self._fetchall = False
        if uri.startswith('sqlite'):
            self._fetchall = True
            self._sqlite = True
        

    def uri_split(self, uri:str=None) -> dict:
        if uri is None:
            uri = self._uri
            
        return re.match('((?P<connector>.*)):\/\/((?P<user>.*):)((?P<pass>.*)@)((?P<host>.*)/)((?P<db>.*))', uri).groupdict()

    def close(self):
        """ Closes the db connection

        """

        self._db.close()
        

    def from_file(self, filename:str):
        """ readin a sql file and execute the content 

        Args:
          filename: file to read from

        Returns:
          None

        Raises:
          error on file not exist or sql errors
        """

        if not os.path.isfile( filename ):
            raise RuntimeError( "Files does not exist '{}'".format( filename ))
        
        file_handle = open(filename, 'r')
        content = file_handle.read()
        file_handle.close()

        for command in content.replace("\n", " ").split(';'):
            if command.strip() == "":
                continue

            
            self.do(command)

    def table_names(self) -> list:
        """ get the names of the tables in the database

        Args:
          None

        returns
          table names in a list

        raises:
          None
        """

        return self._db.get_table_names()

    def table_exist(self, name:str) -> bool:
        q = f"SELECT to_regclass('{name}')"
        table = self._db.get_as_dict( q )
        if table[0]['to_regclass'] is None:
            return False

        return True

    def drop_table(self, table_name) -> None:
        """ Delete a table in a database, useful if resetting it during development """
        self.do("DROP table IF EXISTS {} CASCADE".format( table_name ))


    def drop_tables(self) -> None:
        """ Delete all tables in a database, useful if resetting it during development """
        for table in self.table_names():
            self.drop_table( table )
#            self.do("DROP table IF EXISTS {} CASCADE".format( table ))

            
    def do(self, sql:str) -> None:
        """ execute a query 

        Args:
          sql: query to execute

        returns
          the result of the query

        raises:
          None
        """

        return self._db.query( sql, fetchall=self._fetchall )

    def get_as_dict(self, sql:str) -> dict:
        """ executes a query and returns the data as a dict

        Args:
          sql query to execute
        
        Returns:
          result as a dict, or dict list

        Raises:
          None
        """

        return self.do( sql ).as_dict()
        
    def count(self, sql:str) -> int:
        """ executes a query and returns the number of rows generated 
        
        Args:
          sql query to execute

        Returns:
          nr of rows, 0 if none found

        Raises:
          None

        """

        res = self.do( sql ).all()
        return len( res )

            

    def get(self, table, logic:str='AND', order:str=None, limit:int=None, offset:int=None, **values ) -> dict:
        q = "SELECT * FROM {table} ".format( table = table )

        filters = []

        for key in values.keys():
            if ( values[ key ] is not None):
                if isinstance(values[key], int): 
                    filters.append( " {key} = {value}".format( key=key, value=values[ key ]))
                else:
#                    filters.append( " {key} = '{value}'".format( key=key, value=values[ key ]))
                    filters.append( " {key} = '{value}'".format( key=key, value=re.sub("'", "''", str(values[ key ]))))                

            else:
                filters.append( " {key} is NULL".format( key=key))                

        if ( filters != []):
            q += " WHERE " + "  {} ".format( logic ).join( filters )
           
            
        if order is not None:
            q += " ORDER BY {order}".format( order=order )

        if limit is not None:
            q += " limit {} ".format( limit )

        if offset is not None:
            q += " offset {} ".format( offset )

            
        return self.get_as_dict( q )


    def get_single(self, table, **values ) -> dict:

        values = self.get(table, **values)
        if len( values ) > 1:
            raise RuntimeError('get_single returned multiple values')

        elif len( values ) == 1:
            return values[ 0 ]
        else:
            return None






    def get_all( self, table:str, order:str=None):
        return self.get(table=table, order=order)

    
    def get_by_id(self, table, value ) -> dict:
        return self.get_single( table, id=value)


    def escape_string(self, string):
        if type_utils.is_number(string):
            return "{}".format( string )
        elif string is None:
            return 'NULL'


        string = re.sub(r"'", "''", str(string))
        if self._sqlite:
            string = re.sub(r":", "\\:", str(string))

        return "'{}'".format( string )
    
    
    def get_id(self, table, **values ) -> id:
        ids = []

        for res in self.get(table, **values):
            ids.append( res[ 'id' ])

        if len( ids ) == 0:
            return None
        elif len( ids ) == 1:
            return ids[ 0 ]
        else:
            return  ids

    
    def add( self, table:str, entry:dict):

        if entry == {}:
            raise RuntimeError('No values provided')

        keys = list( entry.keys())
        values = entry.values()

        q = "INSERT INTO {table} ({keys}) VALUES ({values})".format( table = table,
                                                                     keys=",".join(keys),
                                                                     values=",".join(map( self.escape_string, values)))
        self.do( q )



    def add_unique( self, table:str, entry:dict, key:str):
        if entry == {}:
            raise RuntimeError('No values provided')

        ids =  self.get_id( table, **{key:entry[ key ]})

        if ids is not None:
            return ids
        try:
            self.add( table, entry )
        except:
            # Expect the value already to have been added in the mean time...
            pass

        return self.get_id( table, **{key: entry[ key ]})

        
    def add_bulk( self, table:str, entries:list ):


        if entries == [] or entries == {}:
            raise RuntimeError('No values provided')

        all_values = []
        keys = list(entries[ 0 ].keys())

        for entry in entries:

            if  keys  != list(entry.keys()):
                raise RuntimeError( 'Not the same keys in all entries!')

            values = entry.values()
                
            all_values.append( "({values})".format( values=",".join( map(self.escape_string, values))))

        q = "INSERT INTO {table} ({keys}) VALUES {values}".format( table = table,
                                                                   keys=",".join(keys),
                                                                   values=",".join(all_values))
        self.do( q )

                            
                
    def update(self, table:str, entry:dict, conditions:dict):
        
        if entry == {}:
            raise RuntimeError('No values provided')
        
        if conditions == [] :
            raise RuntimeError('No conditions provided')

        updates = []
        
        for key, value in entry.items():
            if ( key in conditions ):
                continue
            
            updates.append( "{key} = {value}".format( key=key, value=self.escape_string(value)))

        conds = []
        for key in conditions:
            #if ( key not in entry ):
            #    raise RuntimeError('condition key not in the entry dict')

            conds.append( "{key} = {value}".format( key=key, value=self.escape_string(conditions[ key ])))


        
        q = "UPDATE {table} set {updates} WHERE {conds}".format( table = table,
                                                                 updates=", ".join(updates),
                                                                 conds=" and ".join(conds))
        self.do( q )





    def delete(self, table:str, id:int):
        
        q = "DELETE FROM  {table} WHERE id = '{id}'".format( table = table,
                                                         id=id)
        self.do( q )


    def purge(self, table:str):
        self.do( f"DELETE FROM  {table}" )



        
